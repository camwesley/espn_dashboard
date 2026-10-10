#!/usr/bin/env python3
"""ESPN player-specific regular-season stats, based on ESPN's common/v3 athlete stats JSON."""
import argparse
import csv
import json
import re
from pathlib import Path

import requests

SPORTS = {"nfl": ("football", "nfl"), "nba": ("basketball", "nba"), "mlb": ("baseball", "mlb"), "nhl": ("hockey", "nhl")}
BASE = "https://site.web.api.espn.com/apis/common/v3/sports"
ROSTER_BASE = "https://site.api.espn.com/apis/site/v2/sports"


def get_json(url, params=None):
    try:
        r = requests.get(url, params=params, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        return r.json()
    except (requests.RequestException, ValueError) as exc:
        raise RuntimeError(f"ESPN request failed for {url}: {exc}") from exc


def roster_players(payload):
    for group in payload.get("athletes", []):
        if not isinstance(group, dict):
            continue
        for athlete in group.get("items", [group] if group.get("id") else []):
            if isinstance(athlete, dict):
                yield athlete


def search_player(sport, name):
    path, league = SPORTS[sport]
    url = f"{ROSTER_BASE}/{path}/{league}/teams"
    teams = get_json(url, {"limit": 100}).get("sports", [{}])[0].get("leagues", [{}])[0].get("teams", [])
    matches = []
    for entry in teams:
        team = entry.get("team", {})
        if not team.get("id"):
            continue
        try:
            roster = get_json(f"{ROSTER_BASE}/{path}/{league}/teams/{team['id']}/roster")
        except RuntimeError:
            continue
        for player in roster_players(roster):
            player_name = player.get("displayName", "")
            if player_name.casefold() == name.casefold():
                matches.append({"id": str(player["id"]), "name": player_name, "team": team.get("displayName", "Unknown")})
    if not matches:
        raise ValueError(f"Player '{name}' not found in active {sport.upper()} team rosters. Try --player-id.")
    if len({p['id'] for p in matches}) > 1:
        raise ValueError(f"Multiple athletes named '{name}' found; specify --player-id. IDs: {[p['id'] for p in matches]}")
    return matches[0]


def parse_season_stats(data, season):
    """Extract ONLY categories[].statistics[] entries with season.year == season.

    Never read category.totals (career), and never use a different year's record.
    """
    if str(next((f.get("value") for f in data.get("filters", []) if f.get("name") == "seasontype"), "")) != "2":
        raise ValueError("ESPN response does not confirm regular-season stats (seasontype=2).")
    result = {}
    for category in data.get("categories", []):
        if not isinstance(category, dict):
            continue
        names = category.get("names", [])
        labels = category.get("displayNames", names)
        matched = [entry for entry in category.get("statistics", []) if isinstance(entry, dict) and str(entry.get("season", {}).get("year")) == str(season)]
        if not matched:
            continue
        if len(matched) > 1:
            raise ValueError(f"Multiple {season} records for category {category.get('name')}; refusing to combine them.")
        values = matched[0].get("stats", [])
        if len(values) != len(names):
            raise ValueError(f"Mismatched stat fields in category {category.get('name')}")
        result[category.get("displayName", category.get("name", "Other"))] = [
            {"key": key, "stat": labels[i] if i < len(labels) else key, "value": value}
            for i, (key, value) in enumerate(zip(names, values))
        ]
    if not result:
        raise ValueError(f"No verified {season} regular-season player statistics in ESPN response.")
    return result


def safe_filename(value):
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")


def export(result, folder):
    folder = Path(folder).expanduser()
    folder.mkdir(parents=True, exist_ok=True)
    stem = f"{safe_filename(result['player'])}_{result['sport']}_{result['season']}"
    json_path = folder / f"{stem}.json"
    csv_path = folder / f"{stem}.csv"
    with json_path.open("w", encoding="utf-8") as fp:
        json.dump(result, fp, indent=2, ensure_ascii=False)
    with csv_path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.writer(fp)
        writer.writerow(["player", "player_id", "sport", "season", "season_type", "category", "stat", "value"])
        for category, stats in result["statistics"].items():
            for item in stats:
                writer.writerow([result["player"], result["player_id"], result["sport"], result["season"], "Regular Season", category, item["stat"], item["value"]])
    return json_path, csv_path


def main():
    parser = argparse.ArgumentParser(description="Get one player's ESPN regular-season stats")
    parser.add_argument("--sport", choices=SPORTS, default="nfl")
    parser.add_argument("--player", help="Player full name; prompted if omitted")
    parser.add_argument("--player-id", help="ESPN athlete ID; bypass roster search")
    parser.add_argument("--season", type=int, default=2026, help="Starting season year, e.g. 2026 for 2026-27 NBA")
    parser.add_argument("--input-json", help="Use an existing athlete stats response instead of fetching ESPN")
    parser.add_argument("--export-dir", default="exports")
    args = parser.parse_args()
    if not args.player:
        args.player = input("Enter player full name: ").strip()
    if not args.player:
        parser.error("A player name is required.")
    try:
        if args.input_json:
            with open(args.input_json, encoding="utf-8") as fp:
                data = json.load(fp)
            if not args.player_id:
                raise ValueError("--input-json requires --player-id so the file can be attributed to the correct player.")
            player = {"id": args.player_id, "name": args.player, "team": "Not verified from input"}
        else:
            player = {"id": args.player_id, "name": args.player, "team": "Unknown"} if args.player_id else search_player(args.sport, args.player)
            sport_path, league = SPORTS[args.sport]
            url = f"{BASE}/{sport_path}/{league}/athletes/{player['id']}/stats"
            data = get_json(url, {"season": args.season, "seasontype": 2, "region": "us", "lang": "en"})
        stats = parse_season_stats(data, args.season)
        result = {"player": player["name"], "player_id": str(player["id"]), "team": player["team"], "sport": args.sport.upper(), "season": args.season, "season_type": "Regular Season", "statistics": stats}
        print(f"\n{result['player']} | {result['sport']} | {args.season} Regular Season")
        for category, entries in stats.items():
            print(f"\n{category.upper()}")
            for entry in entries:
                print(f"  {entry['stat']:<30} {entry['value']}")
        jp, cp = export(result, args.export_dir)
        print(f"\nSaved JSON: {jp}\nSaved CSV:  {cp}")
    except (RuntimeError, ValueError, OSError, KeyError, TypeError) as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    main()

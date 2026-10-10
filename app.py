"""Streamlit ESPN player statistics dashboard."""
import csv
import io
import json
from pathlib import Path

import requests
import streamlit as st
from espn_stats import SPORTS, BASE, get_json, parse_season_stats, search_player

st.set_page_config(page_title="ESPN Player Stats", page_icon="🏟️", layout="wide")
st.markdown("""<style>
.block-container {max-width: 1100px; padding-top: 2rem}
h1 {letter-spacing:-.04em}
[data-testid="stMetric"] {background:#17223812;border:1px solid #8291a330;border-radius:14px;padding:16px}
</style>""", unsafe_allow_html=True)
st.title("🏟️ Player Stats Dashboard")
st.caption("Player-specific ESPN regular-season statistics • 2026 NFL/MLB or 2026–27 NBA/NHL")

@st.cache_data(ttl=3600, show_spinner=False)
def find_player(sport, name):
    return search_player(sport, name)

@st.cache_data(ttl=900, show_spinner=False)
def fetch_player_stats(sport, player_id, season):
    path, league = SPORTS[sport]
    return get_json(f"{BASE}/{path}/{league}/athletes/{player_id}/stats", {
        "season": season, "seasontype": 2, "region": "us", "lang": "en"
    })

def csv_bytes(result):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["player", "player_id", "sport", "season", "season_type", "category", "stat", "value"])
    for category, entries in result["statistics"].items():
        for entry in entries:
            writer.writerow([result["player"], result["player_id"], result["sport"], result["season"], "Regular Season", category, entry["stat"], entry["value"]])
    return output.getvalue().encode("utf-8-sig")

with st.sidebar:
    st.header("Search")
    sport = st.selectbox("League", list(SPORTS), format_func=str.upper)
    season = st.number_input("Season starting year", min_value=2000, max_value=2100, value=2026, step=1)
    player_name = st.text_input("Player full name", placeholder="e.g. Lamar Jackson")
    player_id = st.text_input("ESPN player ID (optional)", placeholder="Skip roster search")
    st.caption("NBA/NHL: 2026 means 2026–27. NFL/MLB: 2026 means 2026.")
    run = st.button("Find player stats", type="primary", use_container_width=True)
    st.divider()
    st.caption("ESPN endpoints are undocumented and may change. A 2026 season entry is required; career and team totals are excluded.")

if run:
    if not player_name.strip():
        st.warning("Enter a player name to continue.")
    else:
        try:
            with st.spinner("Finding player and loading ESPN statistics..."):
                player = ({"id": player_id.strip(), "name": player_name.strip(), "team": "Unverified (ID supplied)"}
                          if player_id.strip() else find_player(sport, player_name.strip()))
                data = fetch_player_stats(sport, str(player["id"]), int(season))
                stats = parse_season_stats(data, int(season))
                result = {"player": player["name"], "player_id": str(player["id"]),
                          "team": player["team"], "sport": sport.upper(), "season": int(season),
                          "season_type": "Regular Season", "statistics": stats}
                st.session_state["result"] = result
        except (requests.RequestException, RuntimeError, ValueError, KeyError, TypeError, IndexError) as exc:
            st.session_state.pop("result", None)
            st.error(f"Unable to retrieve verified player stats: {exc}")
            st.info("Try the exact player name or enter a known ESPN player ID. If the season is absent, no totals will be substituted.")

result = st.session_state.get("result")
if result:
    st.subheader(result["player"])
    st.caption(f"{result['team']} · {result['sport']} · {result['season']} Regular Season · ESPN ID {result['player_id']}")
    key_stats = [("Passing yards", "passingYards"), ("Passing TD", "passingTouchdowns"),
                 ("Interceptions", "interceptions"), ("Rushing yards", "rushingYards")]
    flat = {e["key"]: e["value"] for cat, entries in result["statistics"].items()
            if cat.lower() in ("passing", "rushing") for e in entries}
    highlights = [(label, flat[key]) for label, key in key_stats if key in flat]
    if highlights:
        cols = st.columns(len(highlights))
        for col, (label, value) in zip(cols, highlights):
            col.metric(label, value)
    tabs = st.tabs(list(result["statistics"].keys()))
    for tab, (category, entries) in zip(tabs, result["statistics"].items()):
        with tab:
            st.dataframe([{"Statistic": e["stat"], "Value": e["value"]} for e in entries],
                         hide_index=True, use_container_width=True)
    stem = f"{result['player'].lower().replace(' ', '_')}_{sport}_{season}"
    a, b = st.columns(2)
    with a:
        st.download_button("⬇️ Download CSV", csv_bytes(result), file_name=f"{stem}.csv", mime="text/csv", use_container_width=True)
    with b:
        st.download_button("⬇️ Download JSON", json.dumps(result, indent=2), file_name=f"{stem}.json", mime="application/json", use_container_width=True)
else:
    st.info("Choose a league, enter a player, and click **Find player stats**. The dashboard shows only verified statistics for the selected season.")

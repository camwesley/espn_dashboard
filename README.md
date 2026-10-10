# ESPN Player Stats Web Dashboard

A local Streamlit web interface for the ESPN player stats lookup. Enter any player's full name (or optionally their ESPN ID), choose a league, and see player-only regular-season stats. Download the displayed results as CSV or JSON.

## Start on macOS

```bash
cd ~/Downloads/espn_dashboard
python3 -m pip install -r requirements.txt
python3 -m streamlit run app.py
```

Open the URL printed in Terminal (usually http://localhost:8501). Stop with Ctrl+C.

## Using it

1. Choose NFL, NBA, MLB, or NHL.
2. Enter the player name, e.g. `Patrick Mahomes` or `Lamar Jackson`.
3. Leave ESPN player ID blank for automatic roster search, or enter an ID to bypass the search.
4. Set season to `2026` and click **Find player stats**.
5. View categories and download CSV/JSON.

For NBA and NHL, 2026 denotes the 2026–27 season. NFL and MLB use calendar-year labels.

## How it works

`app.py` provides the dashboard and file downloads. `espn_stats.py` (the previous project) handles ESPN requests, roster lookup, and parsing. The parser selects only `categories[].statistics[]` rows where `season.year == 2026` and confirms `seasontype == 2`. It deliberately ignores `categories[].totals`, which contains career totals.

## Limitations

- ESPN endpoints are undocumented; the service may change them or rate-limit requests.
- Player name search uses active team rosters, so inactive/free-agent players may require an ESPN ID.
- The parser is tested against the supplied NFL 2026 JSON; other leagues' response formats may need adaptation.
- No results are shown when ESPN does not return a verified selected-season block.
- Player IDs entered manually cannot be independently confirmed to match the typed name; the dashboard labels that team's identity as unverified.
- This is a local web dashboard, not a deployed public site or an API server.

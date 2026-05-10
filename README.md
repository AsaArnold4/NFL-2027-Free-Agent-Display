# 2027 NFL Free Agent Tracker — v3

## What's in this build

| # | Feature | Notes |
|---|---------|-------|
| 1 | Sortable table | Sort dropdown above the table (Prior APY ↑↓, Age ↑↓, Projection midpoint, Snap %, Player A-Z) |
| 2 | CSV export | Top-right of Browse tab, exports the current filtered + sorted view |
| 3 | Position Group filter | QB / Skill / OL / DL / LB / DB / ST (per spec) |
| 4 | Tier system | Top 5 / Top 15 / Starter / Backup — thresholds bumped ~18% over 2025 levels for 2027 market |
| 5 | Compare view | Side-by-side cards for 2-3 players + numerical comparison table |
| 6 | Top-by-Position preset | Top N at every position, optional group filter |
| 7 | Cap-space context | Team fits ranked by 2027 effective-cap absorption headroom; pill-styled "Easy fit / Workable / Cap surgery needed" labels |
| 8 | Clickable player rows | Player names are links — clicking sets `?player=slug` in the URL and renders detail panel below the table. Shareable. |
| 9 | Snap % column + filter | Column in main table; Min Snap % slider in sidebar |

## What changed in the design

- **Custom HTML table** replaces `st.dataframe`. Dark navy header with bronze column labels, cream rows, dark pill badges for position, FA Type pill under the player name, bronze-colored projection band with comp-count subtitle, tier pills color-coded by tier severity.
- **All text colors explicit** — every text element on a cream background has an explicit dark color set, no inheritance from Streamlit defaults. Killed the white-on-cream issue.
- **No emojis in fit indicators**. Replaced ✅ green checks with bronze/cream pills: filled bronze for Easy fit, outlined bronze for Workable, muted brick fill for Cap surgery needed.
- **Full team names** in player detail ("Los Angeles Rams" not "LAR — Rams"). 3-letter code still used in the main table column.
- **Pagination restored** — 50 per page, Prev/Next centered, "Showing X-Y of Z · Page A of B".
- **Sidebar restyled** to dark with bronze labels for clear hierarchy against the cream main area.

## Tier thresholds (calibrated to projected 2027 market)

All values in $M of APY. A player gets a tier label by where their *prior* APY would slot at the position.

```
                Top 5   Top 15   Starter
QB              60.0    42.0     18.0
RB              18.0    12.0      6.0
WR              38.0    26.0     12.0
TE              21.0    14.0      6.0
OT              28.0    24.0     14.0
IOL             25.0    19.0      9.0
EDGE            41.0    30.0     14.0
IDL             33.0    24.0     12.0
LB              24.0    18.0      9.0
CB              27.0    21.0     12.0
S               24.0    18.0      9.0
K                7.0     6.0      3.5
P                5.0     3.5      2.5
LS               2.4     1.8      1.5
```

Granular OL positions map to tier keys: LT/RT → OT, LG/RG/C → IOL. FB → RB.

## Files

```
fa_tracker/
├── app.py                          # main Streamlit app
├── app_player_detail.py            # player detail panel
├── data.py                         # loaders, joins, tier + projection logic
├── fa_2027_clean.csv               # FA list (876 players)
├── nfl_players_by_agency_v2.csv    # representation source
├── 2027_team_cap_space.csv         # 2027 team cap space
├── requirements.txt
├── .gitignore
└── README.md
```

## Deploying

1. Push all files to your GitHub repo.
2. Streamlit Cloud auto-redeploys on push if the app is already configured.
3. If new app: point Streamlit Cloud at `app.py` as the main file.

## What to tune

- **`TIER_THRESHOLDS_M`** in `data.py` — current calibration assumes ~18% market growth over 2025. Adjust if your cap-growth assumption differs.
- **`project_apy()`** in `data.py` — simple comp-band median with an age curve. Swap in your real projection engine here; the app reads `projection_low / projection_high / comp_count` and is agnostic to how they're computed.

## Future improvements worth scoping

1. **Persistent watchlist + private notes per player** — needs a small DB layer (SQLite is enough). Biggest single quality-of-life win for daily use.
2. **Market-mover flags** — when a comp signs at a known number, flag every player whose projection used that comp as "comp updated."
3. **Scheme/role tags** on offensive players (vertical / YAC / slot for WR; gap/zone for OL) — makes team-fit logic much smarter than cap space alone.
4. **Multi-year outlook** (2028 / 2029 tabs) using the same projection engine.
5. **Accrued seasons** — when you can pull that data, add an `accrued_seasons` column to the FA CSV and surface it in the player detail.

"""
2027 NFL Free Agent Tracker — Streamlit app.

Features:
    1. Sortable table (sort dropdown above the table)
    2. CSV export of filtered view
    3. Position Group filter (QB / Skill / OL / DL / LB / DB / ST)
    4. Tier system (Top 5 / Top 15 / Starter / Backup, calibrated to 2027)
    5. Compare view (side-by-side, up to 3 players)
    6. Top-by-Position preset
    7. Cap-space context in team fits
    8. Clickable player names → URL-routed detail panel
    9. Snap %  column + Min Snap % filter
"""
from __future__ import annotations

import html as _html
import urllib.parse

import pandas as pd
import streamlit as st

from data import (
    POSITION_GROUPS,
    POSITION_GROUP_ORDER,
    TEAM_CODE_TO_FULL,
    TIER_ORDER,
    build,
)
from app_player_detail import render as render_player_detail

# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="2027 NFL Free Agent Tracker",
    page_icon="🏈",
    layout="wide",
)


def render_html(html_str: str) -> None:
    """Render raw HTML, preferring st.html (Streamlit 1.33+) to avoid the
    Markdown-code-block trap that fires when HTML contains internal blank
    lines and 4+-space indentation."""
    if hasattr(st, "html"):
        st.html(html_str)
    else:
        st.markdown(html_str, unsafe_allow_html=True)


# Hide Streamlit chrome (menu, footer) for a cleaner look
st.markdown(
    """
    <style>
      #MainMenu, footer { visibility: hidden; }
      .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

# Cream-and-bronze theme with explicit text colors everywhere
st.markdown(
    """
    <style>
      :root {
        --bg-cream:        #f6efe3;
        --bg-card:         #ffffff;
        --ink:             #2b1f10;
        --ink-2:           #5a4a30;
        --ink-3:           #8a7a5d;
        --bronze:          #8a4b1a;
        --bronze-2:        #b16a2e;
        --bronze-deep:     #5a3414;
        --rule:            #e7dccb;
        --table-head:      #1a1410;
        --table-head-text: #c89a6e;
        --pill-bg:         #1a1410;
        --pill-text:       #f0e2d0;
        --warn:            #8a3a1a;
      }

      .stApp { background: var(--bg-cream); }
      .stApp, .stApp p, .stApp span, .stApp label, .stApp div { color: var(--ink); }
      .stMarkdown a { color: var(--bronze); }

      /* Hero */
      .hero {
        background: linear-gradient(90deg, var(--bronze-2) 0%, var(--bronze-deep) 100%);
        padding: 28px 32px;
        border-radius: 14px;
        margin-bottom: 18px;
      }
      .hero h1 { margin:0; font-size:28px; color: #fff !important; }
      .hero p  { margin:6px 0 0 0; color: rgba(255,255,255,0.92) !important; }

      /* Metric cards */
      .metric-card {
        background: var(--bg-card);
        border: 1px solid var(--rule);
        border-radius: 10px;
        padding: 14px 16px;
        height: 100%;
      }
      .metric-card .label {
        color: var(--ink-3) !important;
        font-size: 11px;
        letter-spacing: .08em;
        text-transform: uppercase;
      }
      .metric-card .val  {
        font-size: 26px; font-weight: 700;
        color: var(--ink) !important; line-height: 1.1;
        margin-top: 4px;
      }
      .metric-card .sub  {
        font-size: 12px; color: var(--ink-2) !important;
        margin-top: 4px;
      }

      /* Section headings */
      h2, h3, h4, h5 { color: var(--ink) !important; }

      /* === FA TABLE === */
      .fa-table {
        width: 100%;
        border-collapse: collapse;
        background: var(--bg-cream);
        font-size: 14px;
        margin-top: 8px;
      }
      .fa-table thead { background: var(--table-head); }
      .fa-table thead th {
        color: var(--table-head-text) !important;
        padding: 14px 12px;
        text-align: left;
        font-size: 11px;
        letter-spacing: .08em;
        text-transform: uppercase;
        font-weight: 600;
        white-space: nowrap;
      }
      .fa-table thead th:first-child { border-top-left-radius: 8px; }
      .fa-table thead th:last-child  { border-top-right-radius: 8px; }
      .fa-table tbody td {
        padding: 14px 12px;
        border-bottom: 1px solid var(--rule);
        color: var(--ink) !important;
        vertical-align: middle;
      }
      .fa-table tbody tr:hover { background: rgba(177, 106, 46, 0.06); }
      .fa-table .rank-cell { color: var(--ink-3) !important; font-weight: 500; }
      .fa-table .player-cell { min-width: 180px; }
      .fa-table a.player-name {
        color: var(--ink) !important;
        font-weight: 700;
        text-decoration: none;
      }
      .fa-table a.player-name:hover {
        color: var(--bronze) !important;
        text-decoration: underline;
      }
      .fa-table .team-cell, .fa-table .age-cell, .fa-table .snap-cell {
        color: var(--ink-2) !important;
      }
      .fa-table .prior-apy { color: var(--ink) !important; font-weight: 600; }
      .fa-table .projection { color: var(--bronze) !important; font-weight: 600; }
      .fa-table .comps {
        color: var(--ink-3) !important; font-size: 12px; margin-top: 2px;
      }
      .fa-table .rep-cell { color: var(--ink-2) !important; }
      .fa-table .empty-rep { color: var(--ink-3) !important; }

      /* Pills */
      .pos-pill {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 6px;
        background: var(--pill-bg);
        color: var(--pill-text) !important;
        font-size: 12px;
        font-weight: 600;
        letter-spacing: .02em;
      }
      .fa-pill {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 4px;
        background: var(--pill-bg);
        color: var(--pill-text) !important;
        font-size: 10px;
        font-weight: 600;
        letter-spacing: .04em;
        margin-top: 4px;
      }
      .tier-pill {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 999px;
        font-size: 11px;
        font-weight: 600;
        letter-spacing: .04em;
        white-space: nowrap;
      }
      .tier-top5    { background: var(--bronze);   color: var(--bg-cream) !important; }
      .tier-top15   { background: #d4a574;        color: #4a2c0c !important; }
      .tier-starter { background: #e7dccb;        color: #5a4a30 !important; }
      .tier-backup  { background: #ece6d8;        color: #8a7a5d !important; }

      /* Fit pills (replacing the green check emoji) */
      .fit-pill {
        display: inline-block;
        padding: 5px 14px;
        border-radius: 999px;
        font-size: 12px;
        font-weight: 600;
        white-space: nowrap;
      }
      .fit-easy     { background: var(--bronze); color: var(--bg-cream) !important; }
      .fit-workable {
        background: transparent;
        color: var(--bronze) !important;
        border: 1.5px solid var(--bronze);
      }
      .fit-tight    { background: var(--warn); color: var(--bg-cream) !important; }

      /* Player detail card */
      .detail-card {
        background: var(--bg-card);
        border: 1px solid var(--rule);
        border-radius: 10px;
        padding: 18px 20px;
      }
      .detail-card .label {
        color: var(--ink-3) !important;
        font-size: 11px;
        letter-spacing: .08em;
        text-transform: uppercase;
      }
      .detail-card .val {
        color: var(--ink) !important;
        font-weight: 700;
      }
      .detail-card .name {
        font-size: 26px;
        font-weight: 700;
        color: var(--ink) !important;
      }
      .detail-card .proj-band {
        font-size: 30px;
        font-weight: 700;
        color: var(--bronze) !important;
        line-height: 1.1;
      }
      .detail-card hr { border: none; border-top: 1px solid var(--rule); margin: 14px 0; }
      .detail-card .tag {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 999px;
        font-size: 12px;
        font-weight: 600;
        margin-right: 4px;
      }
      .tag-meta { background: #ece6d8; color: var(--ink) !important; }
      .tag-age  { background: #fde9d3; color: #6a3a0e !important; }
      .tag-fa   { background: #efe1c8; color: #6a4a14 !important; }

      .comp-row {
        background: var(--bg-cream);
        border-left: 4px solid var(--bronze-2);
        padding: 8px 12px;
        margin: 6px 0;
        border-radius: 4px;
        color: var(--ink) !important;
      }
      .comp-row .comp-meta { color: var(--ink-2) !important; }

      .fit-row {
        background: var(--bg-card);
        border: 1px solid var(--rule);
        padding: 12px 16px;
        margin: 8px 0;
        border-radius: 8px;
      }
      .fit-row .fit-team {
        font-size: 16px;
        font-weight: 700;
        color: var(--ink) !important;
      }
      .fit-row .fit-meta {
        color: var(--ink-2) !important;
        font-size: 13px;
        margin-top: 4px;
      }
      .fit-row .fit-meta b { color: var(--ink) !important; }

      /* Pagination */
      .page-info {
        text-align: center;
        color: var(--ink-2) !important;
        font-size: 14px;
        padding-top: 8px;
      }

      /* Sidebar tweaks */
      [data-testid="stSidebar"] {
        background: #1a1410;
      }
      [data-testid="stSidebar"] *:not(input):not(.fa-pill):not(.pos-pill):not(.tier-pill) {
        color: #f0e2d0 !important;
      }
      [data-testid="stSidebar"] .stSelectbox label,
      [data-testid="stSidebar"] .stMultiSelect label,
      [data-testid="stSidebar"] .stSlider label,
      [data-testid="stSidebar"] .stCheckbox label,
      [data-testid="stSidebar"] .stTextInput label {
        color: #c89a6e !important;
        font-weight: 600;
        letter-spacing: .04em;
      }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

@st.cache_data
def get_data():
    d = build()
    return d.fa, d.cap, d.agencies

fa_all, cap_df, ag_df = get_data()


# ---------------------------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("### VS — 2027 FA Tracker")
    st.caption("Live valuation, representation, and team-fit context")
    st.divider()

    search = st.text_input("Search", placeholder="Player, team, agent…")

    pos_group_choice = st.multiselect(
        "Position Group",
        options=POSITION_GROUP_ORDER,
        default=[],
        help=("QB, Skill (WR/TE/RB), OL, DL (EDGE/IDL), LB, "
              "DB (CB/S), or ST (K/P/LS)."),
    )

    if pos_group_choice:
        pos_options = sorted({p for g in pos_group_choice for p in POSITION_GROUPS[g]})
        pos_options = [p for p in pos_options if p in fa_all["position"].unique()]
    else:
        pos_options = sorted(fa_all["position"].unique())

    positions = st.multiselect("Position", pos_options, default=[])

    teams = st.multiselect(
        "Team",
        sorted(fa_all["team"].unique()),
        default=[],
    )

    agencies = st.multiselect(
        "Agency",
        sorted([a for a in fa_all["agency_name"].unique() if a != "—"]),
        default=[],
    )

    fa_types = st.multiselect(
        "FA Type",
        sorted(fa_all["fa_type"].unique()),
        default=[],
    )

    tiers = st.multiselect("Tier", TIER_ORDER, default=[])

    min_apy_m = st.slider(
        "Min. Prior APY ($M)",
        min_value=0, max_value=50, value=0, step=1,
    )

    min_snap_pct = st.slider(
        "Min. Snap %",
        min_value=0, max_value=100, value=0, step=5,
        help="Filter out guys who barely played last season.",
    )

    only_vayner = st.checkbox("Show VaynerSports clients only")

    st.divider()
    st.caption(
        "**Sources:** OverTheCap (FA list, cap space, "
        "historical contracts), AthleteAgent.com (representation)."
    )


# ---------------------------------------------------------------------------
# Apply filters
# ---------------------------------------------------------------------------

def apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if search:
        s = search.strip().lower()
        mask = (
            out["player_name"].str.lower().str.contains(s, na=False)
            | out["team"].str.lower().str.contains(s, na=False)
            | out["team_display"].str.lower().str.contains(s, na=False)
            | out["agency_name"].str.lower().str.contains(s, na=False)
        )
        out = out[mask]
    if pos_group_choice:
        out = out[out["position_group"].isin(pos_group_choice)]
    if positions:
        out = out[out["position"].isin(positions)]
    if teams:
        out = out[out["team"].isin(teams)]
    if agencies:
        out = out[out["agency_name"].isin(agencies)]
    if fa_types:
        out = out[out["fa_type"].isin(fa_types)]
    if tiers:
        out = out[out["tier"].isin(tiers)]
    if min_apy_m > 0:
        out = out[out["prior_apy"] >= min_apy_m * 1_000_000]
    if min_snap_pct > 0:
        out = out[out["snap_pct"] >= min_snap_pct]
    if only_vayner:
        out = out[out["is_vaynersports"]]
    return out

fa_filtered = apply_filters(fa_all)


# ---------------------------------------------------------------------------
# Hero + metric cards
# ---------------------------------------------------------------------------

st.markdown(
    '<div class="hero">'
    '<h1>2027 NFL Free Agent Tracker</h1>'
    '<p>Live valuation, representation, and team-fit context for every upcoming free agent</p>'
    '</div>',
    unsafe_allow_html=True,
)

c1, c2, c3, c4 = st.columns(4)
top_apy_player = fa_filtered.iloc[0] if len(fa_filtered) else None
cards = [
    ("Free Agents", f"{len(fa_filtered):,}", "matching filters"),
    ("Top Prior APY",
     f"${top_apy_player['prior_apy']/1e6:.0f}M" if top_apy_player is not None else "—",
     top_apy_player['player_name'] if top_apy_player is not None else ""),
    ("VaynerSports Clients",
     f"{int(fa_filtered['is_vaynersports'].sum())}",
     "in current view"),
    ("Agencies Repped",
     f"{fa_filtered.loc[fa_filtered['agency_name'] != '—', 'agency_name'].nunique()}",
     "across current view"),
]
for col, (label, val, sub) in zip([c1, c2, c3, c4], cards):
    col.markdown(
        '<div class="metric-card">'
        f'<div class="label">{label}</div>'
        f'<div class="val">{val}</div>'
        f'<div class="sub">{sub}</div>'
        '</div>',
        unsafe_allow_html=True,
    )

st.write("")

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab_browse, tab_top, tab_compare = st.tabs(["Browse", "Top by Position", "Compare"])


# =============================================================================
# Helpers — table rendering (single-line HTML output, no newlines)
# =============================================================================

TIER_CLASS = {
    "Top 5":   "tier-top5",
    "Top 15":  "tier-top15",
    "Starter": "tier-starter",
    "Backup":  "tier-backup",
}


def render_fa_table(df: pd.DataFrame) -> str:
    """
    Render a styled HTML table from a frame of FA rows.

    IMPORTANT: returns a single-line HTML string with no internal newlines.
    Multi-line/indented HTML in a Streamlit markdown call can trigger a
    code-block render, so we avoid that pattern entirely.
    """
    if df.empty:
        return ('<div style="padding:40px;text-align:center;color:#5a4a30">'
                'No free agents match the current filters.</div>')

    parts = [
        '<table class="fa-table">',
        '<thead><tr>',
        '<th>#</th><th>Player</th><th>Pos</th><th>Team</th>',
        '<th>Age</th><th>Snap %</th><th>Tier</th>',
        '<th>Prior APY</th><th>2027 Projection</th><th>Representation</th>',
        '</tr></thead>',
        '<tbody>',
    ]

    for _, r in df.iterrows():
        name_esc   = _html.escape(str(r["player_name"]))
        slug       = urllib.parse.quote(str(r["slug"]))
        pos_esc    = _html.escape(str(r["position"]))
        team_esc   = _html.escape(str(r["team"]))
        ag_esc     = _html.escape(str(r["agency_name"]))
        fa_type    = _html.escape(str(r["fa_type"]))
        tier_str   = str(r["tier"])
        tier_class = TIER_CLASS.get(tier_str, "tier-backup")

        if r["projection_low"] > 0:
            proj_str = (f'${r["projection_low"]/1e6:.1f}M – '
                        f'${r["projection_high"]/1e6:.1f}M')
            comps_str = f'{int(r["comp_count"])} comps'
        else:
            proj_str  = "—"
            comps_str = "no comps"

        rep_html = ('<span class="empty-rep">—</span>'
                    if r["agency_name"] == "—" else ag_esc)

        parts.append(
            '<tr>'
            f'<td class="rank-cell">#{int(r["rank"])}</td>'
            '<td class="player-cell">'
            f'<a class="player-name" href="?player={slug}">{name_esc}</a>'
            f'<div><span class="fa-pill">{fa_type}</span></div>'
            '</td>'
            f'<td><span class="pos-pill">{pos_esc}</span></td>'
            f'<td class="team-cell">{team_esc}</td>'
            f'<td class="age-cell">{int(r["age"])}</td>'
            f'<td class="snap-cell">{r["snap_pct"]:.0f}%</td>'
            f'<td><span class="tier-pill {tier_class}">{tier_str}</span></td>'
            f'<td class="prior-apy">${r["prior_apy"]/1e6:.1f}M</td>'
            '<td>'
            f'<div class="projection">{proj_str}</div>'
            f'<div class="comps">{comps_str}</div>'
            '</td>'
            f'<td class="rep-cell">{rep_html}</td>'
            '</tr>'
        )

    parts.append('</tbody></table>')
    return ''.join(parts)


# =============================================================================
# TAB 1 — Browse
# =============================================================================
with tab_browse:
    # URL routing for player detail
    selected_slug = st.query_params.get("player", None)

    # Sort + export row
    cs1, cs2, cs3 = st.columns([2.5, 1.5, 1])
    with cs1:
        st.markdown(
            f"<div style='padding-top:8px'><b>{len(fa_filtered):,}</b> of "
            f"<b>{len(fa_all):,}</b> free agents</div>",
            unsafe_allow_html=True,
        )
    with cs2:
        sort_choice = st.selectbox(
            "Sort by",
            [
                "Prior APY (high → low)",
                "Prior APY (low → high)",
                "2027 Projection midpoint (high → low)",
                "Age (young → old)",
                "Age (old → young)",
                "Snap % (high → low)",
                "Player A → Z",
            ],
            label_visibility="collapsed",
        )
    with cs3:
        st.download_button(
            "⬇  Export CSV",
            data=fa_filtered.drop(columns=["agency_url"], errors="ignore")
                  .to_csv(index=False).encode("utf-8"),
            file_name="free_agents_2027_filtered.csv",
            mime="text/csv",
            use_container_width=True,
        )

    # Apply sort
    sort_map = {
        "Prior APY (high → low)":              ("prior_apy", False),
        "Prior APY (low → high)":              ("prior_apy", True),
        "2027 Projection midpoint (high → low)": (None,      False),
        "Age (young → old)":                   ("age", True),
        "Age (old → young)":                   ("age", False),
        "Snap % (high → low)":                 ("snap_pct", False),
        "Player A → Z":                        ("player_name", True),
    }
    if sort_choice == "2027 Projection midpoint (high → low)":
        fa_view = fa_filtered.assign(
            _mid=(fa_filtered["projection_low"] + fa_filtered["projection_high"]) / 2
        ).sort_values("_mid", ascending=False).drop(columns="_mid")
    else:
        col, asc = sort_map[sort_choice]
        fa_view = fa_filtered.sort_values(col, ascending=asc)

    # Pagination (50 per page)
    PAGE_SIZE = 50
    total_pages = max(1, (len(fa_view) + PAGE_SIZE - 1) // PAGE_SIZE)
    if "page" not in st.session_state:
        st.session_state.page = 1
    st.session_state.page = min(st.session_state.page, total_pages)

    pc1, pc2, pc3 = st.columns([1, 3, 1])
    with pc1:
        if st.button("← Prev", disabled=st.session_state.page <= 1,
                     use_container_width=True):
            st.session_state.page -= 1
            st.rerun()
    with pc2:
        start = (st.session_state.page - 1) * PAGE_SIZE + 1
        end   = min(start + PAGE_SIZE - 1, len(fa_view))
        if len(fa_view) == 0:
            st.markdown('<div class="page-info">No results</div>',
                        unsafe_allow_html=True)
        else:
            st.markdown(
                f'<div class="page-info">Showing {start}–{end} of '
                f'{len(fa_view):,} &middot; Page {st.session_state.page} '
                f'of {total_pages}</div>',
                unsafe_allow_html=True,
            )
    with pc3:
        if st.button("Next →", disabled=st.session_state.page >= total_pages,
                     use_container_width=True):
            st.session_state.page += 1
            st.rerun()

    # Render the visible page
    page_slice = fa_view.iloc[(st.session_state.page - 1) * PAGE_SIZE :
                              st.session_state.page * PAGE_SIZE]
    render_html(render_fa_table(page_slice))

    # Player detail (if URL has ?player=slug)
    if selected_slug:
        matches = fa_all[fa_all["slug"] == selected_slug]
        if len(matches):
            player_row = matches.iloc[0]
            st.divider()
            back_l, back_r = st.columns([1, 5])
            with back_l:
                if st.button("← Back to list", use_container_width=True):
                    st.query_params.clear()
                    st.rerun()
            with back_r:
                st.markdown(
                    f"<div style='padding-top:6px;color:#5a4a30'>"
                    f"Viewing <b>{_html.escape(str(player_row['player_name']))}</b>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            render_player_detail(player_row, fa_all, cap_df)


# =============================================================================
# TAB 2 — Top by Position
# =============================================================================
with tab_top:
    st.markdown("#### Top by position")
    st.caption("One-click view of the top N at every position. "
               "Useful for building positional shortlists.")

    cc1, cc2 = st.columns([1, 3])
    with cc1:
        top_n = st.number_input("Top N per position", min_value=3, max_value=25,
                                value=10, step=1)
    with cc2:
        group_pick = st.multiselect(
            "Limit to position group(s)",
            options=POSITION_GROUP_ORDER,
            default=[],
        )

    base = fa_all.copy()
    if group_pick:
        base = base[base["position_group"].isin(group_pick)]

    top_per_pos = (
        base.sort_values(["position", "prior_apy"], ascending=[True, False])
            .groupby("position", group_keys=False)
            .head(top_n)
    )

    positions_present = sorted(top_per_pos["position"].unique())
    cols = st.columns(2)
    for i, pos in enumerate(positions_present):
        block = top_per_pos[top_per_pos["position"] == pos]
        with cols[i % 2]:
            st.markdown(f"##### {pos} — top {len(block)}")
            render_html(render_fa_table(block))
            st.write("")


# =============================================================================
# TAB 3 — Compare
# =============================================================================

def render_compare_card(r: pd.Series) -> str:
    """Single-line HTML for a Compare-tab player card. Same anti-newline rule."""
    tier_str = str(r["tier"])
    tier_cls = TIER_CLASS.get(tier_str, "tier-backup")
    proj_str = (f'${r["projection_low"]/1e6:.1f}M – ${r["projection_high"]/1e6:.1f}M'
                if r["projection_low"] > 0 else "—")
    return (
        '<div class="detail-card">'
        f'<div class="name">{_html.escape(str(r["player_name"]))}</div>'
        '<div style="margin-top:6px">'
        f'<span class="tag tag-meta">{_html.escape(str(r["position"]))}</span>'
        f'<span class="tag tag-meta">{_html.escape(str(r["team"]))}</span>'
        f'<span class="tag tag-age">Age {int(r["age"])}</span>'
        f'<span class="tag tag-fa">{_html.escape(str(r["fa_type"]))}</span>'
        '</div>'
        '<hr/>'
        '<div class="label">Prior APY</div>'
        f'<div class="val" style="font-size:22px">${r["prior_apy"]/1e6:.1f}M</div>'
        '<div class="label" style="margin-top:10px">2027 Projection</div>'
        f'<div class="proj-band" style="font-size:22px">{proj_str}</div>'
        f'<div style="color:#8a7a5d;font-size:12px;margin-top:2px">'
        f'{int(r["comp_count"])} comps</div>'
        '<div class="label" style="margin-top:10px">Tier</div>'
        f'<div><span class="tier-pill {tier_cls}">{tier_str}</span></div>'
        '<div class="label" style="margin-top:10px">Snap %</div>'
        f'<div class="val">{r["snap_pct"]:.0f}%</div>'
        '<div class="label" style="margin-top:10px">Representation</div>'
        f'<div class="val" style="font-weight:500">'
        f'{_html.escape(str(r["agency_name"]))}</div>'
        '</div>'
    )


with tab_compare:
    st.markdown("#### Compare players")
    st.caption("Pick 2 or 3 players to evaluate side by side.")

    names = fa_all["player_name"].tolist()
    picks = st.multiselect(
        "Players",
        options=names,
        max_selections=3,
        placeholder="Search and select 2-3 players…",
    )

    if len(picks) < 2:
        st.info("Select at least 2 players to compare.")
    else:
        compare_rows = fa_all[fa_all["player_name"].isin(picks)]
        compare_rows = compare_rows.set_index("player_name").loc[picks].reset_index()

        cols = st.columns(len(picks))
        for col, (_, r) in zip(cols, compare_rows.iterrows()):
            with col:
                render_html(render_compare_card(r))

        st.divider()
        st.markdown("##### Numerical comparison")
        cmp_tbl = compare_rows[[
            "player_name", "position", "team", "age", "snap_pct", "fa_type",
            "prior_apy", "projection_low", "projection_high",
            "comp_count", "tier", "agency_name"
        ]].copy()
        cmp_tbl["prior_apy"]       = cmp_tbl["prior_apy"].apply(lambda v: f"${v/1e6:.1f}M")
        cmp_tbl["projection_low"]  = cmp_tbl["projection_low"].apply(lambda v: f"${v/1e6:.1f}M")
        cmp_tbl["projection_high"] = cmp_tbl["projection_high"].apply(lambda v: f"${v/1e6:.1f}M")
        cmp_tbl["snap_pct"]        = cmp_tbl["snap_pct"].apply(lambda v: f"{v:.0f}%")
        cmp_tbl = cmp_tbl.rename(columns={
            "player_name": "Player", "position": "Pos", "team": "Team",
            "age": "Age", "snap_pct": "Snap %", "fa_type": "FA Type",
            "prior_apy": "Prior APY",
            "projection_low": "Proj Low", "projection_high": "Proj High",
            "comp_count": "Comps", "tier": "Tier", "agency_name": "Representation",
        }).set_index("Player").T
        st.dataframe(cmp_tbl, use_container_width=True)

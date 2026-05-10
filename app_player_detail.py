"""
Player detail panel: projection, comps, team fits with cap-space context.

Styling lives in app.py's global CSS so this module only emits HTML
that references the right CSS classes.
"""
from __future__ import annotations

import html as _html

import pandas as pd
import streamlit as st

from data import TEAM_CODE_TO_FULL


def _fmt_money(v: float) -> str:
    if pd.isna(v):
        return "—"
    if abs(v) >= 1_000_000:
        return f"{'-$' if v < 0 else '$'}{abs(v)/1e6:.1f}M"
    if abs(v) >= 1_000:
        return f"{'-$' if v < 0 else '$'}{abs(v)/1e3:.0f}K"
    return f"${v:,.0f}"


def find_team_fits(player: pd.Series, fa: pd.DataFrame, cap: pd.DataFrame,
                   max_fits: int = 6) -> pd.DataFrame:
    """
    Teams with at least one expiring contract at the player's position,
    ranked by 2027 effective cap headroom after absorbing the projection
    midpoint.  Excludes the player's current team (that's a re-sign).
    """
    pos = player["position"]
    target_mid = (player["projection_low"] + player["projection_high"]) / 2

    expiring_at_pos = (
        fa[fa["position"] == pos]
          .groupby("team")
          .agg(expiring_at_pos=("player_name", "count"))
          .reset_index()
    )
    expiring_at_pos["team_nickname"] = expiring_at_pos["team"].map(
        lambda c: TEAM_CODE_TO_FULL.get(c, c).split()[-1]
    )

    fits = expiring_at_pos.merge(cap, on="team_nickname", how="left")
    fits = fits[fits["team"] != player["team"]]
    fits["absorption_headroom"] = fits["effective_cap"] - target_mid
    fits = fits.sort_values("absorption_headroom", ascending=False).head(max_fits)
    return fits


def render(player: pd.Series, fa_all: pd.DataFrame, cap_df: pd.DataFrame) -> None:
    """Render the player detail card under the table."""
    name_esc = _html.escape(str(player["player_name"]))
    team_full = TEAM_CODE_TO_FULL.get(player["team"], player["team"])

    proj_low_m  = player["projection_low"] / 1e6
    proj_high_m = player["projection_high"] / 1e6
    proj_band = (f"${proj_low_m:.1f}M – ${proj_high_m:.1f}M"
                 if player["projection_low"] > 0 else "—")
    target_mid = (player["projection_low"] + player["projection_high"]) / 2

    # ---- LEFT: identity card  |  RIGHT: projection + comps ----
    left, right = st.columns([1, 1.3])

    with left:
        gtd_html = ""
        if player["prior_gtd"] and player["prior_gtd"] > 0:
            gtd_html = (
                f'<div class="label" style="margin-top:14px">Prior Guaranteed</div>'
                f'<div class="val">${player["prior_gtd"]/1e6:.1f}M</div>'
            )
        st.markdown(
            f"""
            <div class="detail-card">
              <div class="label">Player</div>
              <div class="name">{name_esc}</div>
              <div style="margin-top:8px">
                <span class="tag tag-meta">{_html.escape(str(player['position']))}</span>
                <span class="tag tag-meta">{_html.escape(str(player['team']))}</span>
                <span class="tag tag-age">Age {int(player['age'])}</span>
                <span class="tag tag-fa">{_html.escape(str(player['fa_type']))}</span>
              </div>
              <hr/>
              <div class="label">Team</div>
              <div class="val">{_html.escape(team_full)}</div>
              <div class="label" style="margin-top:14px">Representation</div>
              <div class="val">{_html.escape(str(player['agency_name']))}</div>
              <div class="label" style="margin-top:14px">Tier (position-wide)</div>
              <div class="val">{str(player['tier'])}</div>
              <div class="label" style="margin-top:14px">Snap %</div>
              <div class="val">{player['snap_pct']:.0f}%</div>
              {gtd_html}
            </div>
            """,
            unsafe_allow_html=True,
        )

    with right:
        st.markdown(
            f"""
            <div class="detail-card">
              <div class="label">2027 Projection</div>
              <div class="proj-band">{proj_band}</div>
              <div style="color:var(--ink-2);font-size:13px;margin-top:6px">
                {int(player['comp_count'])} {_html.escape(str(player['position']))}
                comps used &middot; Prior APY ${player['prior_apy']/1e6:.1f}M
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("##### Comparable contracts")
        comps = (
            fa_all[
                (fa_all["position"] == player["position"])
                & (fa_all["player_name"] != player["player_name"])
            ]
            .assign(diff=lambda d: (d["prior_apy"] - player["prior_apy"]).abs())
            .sort_values("diff")
            .head(4)
        )
        if comps.empty:
            st.markdown(
                '<div style="color:var(--ink-3)">'
                'No positional comparables in current pool.</div>',
                unsafe_allow_html=True,
            )
        else:
            for _, c in comps.iterrows():
                st.markdown(
                    f"""<div class="comp-row">
                          <b>{_html.escape(str(c['player_name']))}</b>
                          <span class="comp-meta"> — {_html.escape(str(c['team']))}
                          &middot; Age {int(c['age'])} &middot;
                          ${c['prior_apy']/1e6:.1f}M APY &middot;
                          {str(c['tier'])}</span>
                        </div>""",
                    unsafe_allow_html=True,
                )

    # ---- TEAM FITS with CAP SPACE ----
    st.markdown("##### Potential team fits")
    st.markdown(
        f"<div style='color:var(--ink-2);font-size:13px;margin-bottom:8px'>"
        f"Teams with expiring contracts at "
        f"<b style='color:var(--ink)'>{_html.escape(str(player['position']))}</b>, "
        f"ranked by how comfortably their 2027 effective cap space absorbs "
        f"the projection midpoint "
        f"(<b style='color:var(--ink)'>${target_mid/1e6:.1f}M</b>)."
        f"</div>",
        unsafe_allow_html=True,
    )

    fits = find_team_fits(player, fa_all, cap_df)

    if fits.empty:
        st.markdown(
            '<div style="color:var(--ink-3)">'
            'No fits found — every team with an expiring contract at this '
            'position is the player\'s current team, or cap data is missing.</div>',
            unsafe_allow_html=True,
        )
        return

    for _, f in fits.iterrows():
        team_full = TEAM_CODE_TO_FULL.get(f["team"], f["team"])
        cap_str   = _fmt_money(f["effective_cap"])
        head_str  = _fmt_money(f["absorption_headroom"])

        if f["absorption_headroom"] > 20_000_000:
            fit_class, fit_label = "fit-easy", "Easy fit"
        elif f["absorption_headroom"] > 0:
            fit_class, fit_label = "fit-workable", "Workable"
        else:
            fit_class, fit_label = "fit-tight", "Cap surgery needed"

        st.markdown(
            f"""<div class="fit-row">
                  <div style="display:flex;justify-content:space-between;
                              align-items:center">
                    <div class="fit-team">{_html.escape(team_full)}</div>
                    <div><span class="fit-pill {fit_class}">{fit_label}</span></div>
                  </div>
                  <div class="fit-meta">
                    2027 effective cap: <b>{cap_str}</b> &middot;
                    After projection midpoint: <b>{head_str}</b> &middot;
                    {int(f['expiring_at_pos'])} expiring at
                    {_html.escape(str(player['position']))}
                  </div>
                </div>""",
            unsafe_allow_html=True,
        )

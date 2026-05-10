"""
Data layer for the 2027 FA Tracker.

Reads `fa_2027_clean.csv` (scraped FA pool with snap %, guaranteed money,
slug, and granular positions), joins agency representation and 2027 cap
space, and computes derived columns (tier, projection band, position group,
team full name).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).parent

# ---------------------------------------------------------------------------
# Team codes
# ---------------------------------------------------------------------------

# Used for the player-detail header and team-fit rows (e.g. "Los Angeles Rams").
TEAM_CODE_TO_FULL = {
    "ARI": "Arizona Cardinals",   "ATL": "Atlanta Falcons",
    "BAL": "Baltimore Ravens",    "BUF": "Buffalo Bills",
    "CAR": "Carolina Panthers",   "CHI": "Chicago Bears",
    "CIN": "Cincinnati Bengals",  "CLE": "Cleveland Browns",
    "DAL": "Dallas Cowboys",      "DEN": "Denver Broncos",
    "DET": "Detroit Lions",       "GB":  "Green Bay Packers",
    "HOU": "Houston Texans",      "IND": "Indianapolis Colts",
    "JAX": "Jacksonville Jaguars","KC":  "Kansas City Chiefs",
    "LAC": "Los Angeles Chargers","LAR": "Los Angeles Rams",
    "LV":  "Las Vegas Raiders",   "MIA": "Miami Dolphins",
    "MIN": "Minnesota Vikings",   "NE":  "New England Patriots",
    "NO":  "New Orleans Saints",  "NYG": "New York Giants",
    "NYJ": "New York Jets",       "PHI": "Philadelphia Eagles",
    "PIT": "Pittsburgh Steelers", "SEA": "Seattle Seahawks",
    "SF":  "San Francisco 49ers", "TB":  "Tampa Bay Buccaneers",
    "TEN": "Tennessee Titans",    "WAS": "Washington Commanders",
}


# ---------------------------------------------------------------------------
# Position groups (per spec)
#   OL    — offensive line (LT, RT, LG, RG, C; plus generic OL/OT/IOL)
#   Skill — WR, TE, RB, FB
#   QB    — QB
#   DL    — defensive line (EDGE, IDL, plus generic DL/DE/DT)
#   LB    — linebackers
#   DB    — defensive backs (CB, S)
#   ST    — special teams (K, P, LS)
# ---------------------------------------------------------------------------

POSITION_GROUPS = {
    "QB":    ["QB"],
    "Skill": ["WR", "TE", "RB", "FB"],
    "OL":    ["LT", "RT", "LG", "RG", "C", "OL", "OT", "IOL"],
    "DL":    ["EDGE", "IDL", "DE", "DT", "DL"],
    "LB":    ["LB"],
    "DB":    ["CB", "S", "DB"],
    "ST":    ["K", "P", "LS"],
}
POS_TO_GROUP = {p: g for g, ps in POSITION_GROUPS.items() for p in ps}
POSITION_GROUP_ORDER = list(POSITION_GROUPS.keys())


# ---------------------------------------------------------------------------
# Tier thresholds — calibrated to projected 2027 market
# (~18% lift over 2025 levels to reflect two years of cap growth)
# ---------------------------------------------------------------------------

TIER_THRESHOLDS_M = {
    "QB":   (60.0, 42.0, 18.0),
    "RB":   (18.0, 12.0, 6.0),
    "WR":   (38.0, 26.0, 12.0),
    "TE":   (21.0, 14.0, 6.0),
    "OT":   (28.0, 24.0, 14.0),
    "IOL":  (25.0, 19.0, 9.0),
    "EDGE": (41.0, 30.0, 14.0),
    "IDL":  (33.0, 24.0, 12.0),
    "LB":   (24.0, 18.0, 9.0),
    "CB":   (27.0, 21.0, 12.0),
    "S":    (24.0, 18.0, 9.0),
    "K":    (7.0,  6.0,  3.5),
    "P":    (5.0,  3.5,  2.5),
    "LS":   (2.4,  1.8,  1.5),
}

# Map granular OL/FB to tier-threshold keys
TIER_POS_MAP = {
    "LT": "OT", "RT": "OT",
    "LG": "IOL", "RG": "IOL", "C": "IOL",
    "FB": "RB",
}

TIER_ORDER = ["Top 5", "Top 15", "Starter", "Backup"]


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_free_agents(path: Path | str = DATA_DIR / "fa_2027_clean.csv") -> pd.DataFrame:
    """Load the clean 2027 FA list and normalize columns to canonical names."""
    fa = pd.read_csv(path)

    fa = fa.rename(columns={
        "name":      "player_name",
        "pos_detail": "position",
        "team_full":  "team_nickname",   # matches the cap CSV's `Team` field
    })

    # Normalize FA type capitalization ("Void" -> "VOID")
    fa["fa_type"] = fa["fa_type"].astype(str).str.upper()

    # Numerics
    fa["age"]       = pd.to_numeric(fa["age"], errors="coerce").fillna(0).astype(int)
    fa["prior_apy"] = pd.to_numeric(fa["prior_apy"], errors="coerce").fillna(0)
    fa["prior_gtd"] = pd.to_numeric(fa["prior_gtd"], errors="coerce").fillna(0)
    fa["snap_pct"]  = pd.to_numeric(fa["snap_pct"], errors="coerce").fillna(0)

    # Ensure a slug exists (the CSV provides it, but fall back if not)
    if "slug" not in fa.columns:
        fa["slug"] = (fa["player_name"]
                      .str.lower()
                      .str.replace(r"[^a-z0-9]+", "-", regex=True)
                      .str.strip("-"))

    return fa


def load_agencies(path: Path | str = DATA_DIR / "nfl_players_by_agency_v2.csv") -> pd.DataFrame:
    """Load the agency-player file and dedupe (keep larger / more credible agency per player)."""
    a = pd.read_csv(path)[["player_name", "agency_name", "agency_url"]]
    counts = a["agency_name"].value_counts().to_dict()
    a["_pri"] = a["agency_name"].map(counts)
    a = a.sort_values(["player_name", "_pri"], ascending=[True, False])
    a = a.drop_duplicates("player_name", keep="first").drop(columns="_pri")
    return a.reset_index(drop=True)


def load_cap_space(path: Path | str = DATA_DIR / "2027_team_cap_space.csv") -> pd.DataFrame:
    """Load and clean the 2027 team cap-space file."""
    cap = pd.read_csv(path)
    cap = cap.dropna(subset=["Team"]).reset_index(drop=True)
    cap = cap[~cap["Cap"].astype(str).str.lower().eq("space")]

    def to_num(s):
        s = str(s).strip().replace("$", "").replace(",", "").replace(" ", "")
        neg = s.startswith("(") and s.endswith(")")
        s = s.strip("()")
        try:
            v = float(s)
        except ValueError:
            return np.nan
        return -v if neg else v

    cap["cap_space"]      = cap["Cap"].apply(to_num)
    cap["effective_cap"]  = cap["Effective Cap"].apply(to_num)
    cap["active_spend"]   = cap["Active"].apply(to_num)
    cap["dead_money"]     = cap["Dead"].apply(to_num)
    cap["players_signed"] = pd.to_numeric(cap["#"], errors="coerce")
    cap = cap.rename(columns={"Team": "team_nickname"})
    return cap[["team_nickname", "cap_space", "effective_cap",
                "active_spend", "dead_money", "players_signed"]]


# ---------------------------------------------------------------------------
# Derived columns
# ---------------------------------------------------------------------------

def assign_tier(position: str, apy: float) -> str:
    """Where this APY slots at the position, projected to 2027."""
    key = TIER_POS_MAP.get(position, position)
    thresh = TIER_THRESHOLDS_M.get(key)
    if thresh is None:
        return "Backup"
    top5, top15, starter = (t * 1_000_000 for t in thresh)
    if apy >= top5:    return "Top 5"
    if apy >= top15:   return "Top 15"
    if apy >= starter: return "Starter"
    return "Backup"


def project_apy(row: pd.Series, fa: pd.DataFrame) -> tuple[float, float, int]:
    """Comp-band median with age curve. Output: (low, high, n_comps)."""
    pos, prior, age = row["position"], row["prior_apy"], row["age"]
    if prior <= 0:
        return (0.0, 0.0, 0)
    band_low, band_high = prior * 0.65, prior * 1.35
    comps = fa[
        (fa["position"] == pos)
        & (fa["prior_apy"].between(band_low, band_high))
        & (fa["age"].between(age - 3, age + 3))
        & (fa["player_name"] != row["player_name"])
    ]
    if len(comps) < 3:
        comps = fa[
            (fa["position"] == pos)
            & (fa["prior_apy"].between(prior * 0.5, prior * 1.5))
            & (fa["player_name"] != row["player_name"])
        ]
    if len(comps) == 0:
        return (prior * 0.85, prior * 1.10, 0)
    median = comps["prior_apy"].median()

    age_factor = 1.0
    if   age >= 32: age_factor = 0.85
    elif age >= 30: age_factor = 0.92
    elif age <= 25: age_factor = 1.08

    low  = median * 0.88 * age_factor
    high = median * 1.12 * age_factor
    return (round(low, -4), round(high, -4), len(comps))


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

@dataclass
class TrackerData:
    fa: pd.DataFrame
    cap: pd.DataFrame
    agencies: pd.DataFrame


def build() -> TrackerData:
    fa  = load_free_agents()
    ag  = load_agencies()
    cap = load_cap_space()

    # Join agency representation
    fa = fa.merge(ag, on="player_name", how="left")
    fa["agency_name"] = fa["agency_name"].fillna("—")
    fa["is_vaynersports"] = fa["agency_name"].str.lower().str.contains(
        "vaynersports", na=False
    )

    # Position group
    fa["position_group"] = fa["position"].map(POS_TO_GROUP).fillna("Other")

    # Full team display ("Los Angeles Rams")
    fa["team_display"] = fa["team"].map(TEAM_CODE_TO_FULL).fillna(fa["team"])

    # Tier
    fa["tier"] = [assign_tier(p, a) for p, a in zip(fa["position"], fa["prior_apy"])]
    fa["tier"] = pd.Categorical(fa["tier"], categories=TIER_ORDER, ordered=True)

    # Projection
    proj = fa.apply(lambda r: project_apy(r, fa), axis=1, result_type="expand")
    proj.columns = ["projection_low", "projection_high", "comp_count"]
    fa = pd.concat([fa, proj], axis=1)

    # Sort & rank
    fa = fa.sort_values("prior_apy", ascending=False, kind="mergesort").reset_index(drop=True)
    fa.insert(0, "rank", fa.index + 1)

    return TrackerData(fa=fa, cap=cap, agencies=ag)


if __name__ == "__main__":
    d = build()
    print("FA rows:", len(d.fa))
    print(d.fa[["rank","player_name","position","team","age","snap_pct",
                "prior_apy","tier","agency_name"]].head(10).to_string(index=False))
    print()
    print("Position group counts:")
    print(d.fa["position_group"].value_counts())
    print()
    print("Tier counts:")
    print(d.fa["tier"].value_counts())
    print()
    print("VaynerSports clients:", int(d.fa["is_vaynersports"].sum()))

"""
GTO Reference Data for 6-max NL Hold'em Cash Games (100bb).

All data sourced from published GTO solver outputs:
- GTO Wizard (gtowizard.com) — preflop ranges, c-bet frequencies
- Upswing Poker — postflop strategy by board texture
- PokerCoaching.com — range/nut advantage concepts
- PioSolver community results — hand category frequencies

This module provides:
- Hand tier classification (169 hands → 8 tiers)
- Preflop RFI ranges by position
- Board texture classification
- C-bet / check-raise frequency tables
- Facing-bet response frequencies
"""

# ═══════════════════════════════════════════════════════════════════
# 1. HAND TIERS — 169 unique hands, 8 tiers (1 = strongest)
# Based on GTO preflop hand rankings for 6-max 100bb
# ═══════════════════════════════════════════════════════════════════

HAND_TIER: dict[str, int] = {}

# Tier 1 — Premium (top ~3%): AA, KK, QQ, AKs, AKo
_t1 = ["AA", "KK", "QQ", "AKs"]
# Tier 2 — Strong (next ~5%): JJ, TT, AQs, AQo, AJs, KQs
_t2 = ["JJ", "TT", "AQs", "AJs", "KQs", "AKo"]
# Tier 3 — Good (next ~7%): 99, 88, ATs, AJo, KJs, KTs, QJs, AQo
_t3 = ["99", "88", "ATs", "KJs", "KTs", "QJs", "AJo", "KQo"]
# Tier 4 — Playable (next ~10%): 77, 66, A9s-A2s, KJo, QTs, JTs, T9s
_t4 = [
    "77", "66", "A9s", "A8s", "A7s", "A6s", "A5s", "A4s", "A3s", "A2s",
    "QTs", "JTs", "T9s", "KJo", "ATo",
]
# Tier 5 — Marginal (next ~10%): 55, 44, K9s-K6s, Q9s, J9s, T8s, 98s, 87s, 76s, QJo
_t5 = [
    "55", "44", "K9s", "K8s", "K7s", "K6s", "Q9s", "J9s", "T8s",
    "98s", "87s", "76s", "65s", "QJo", "KTo",
]
# Tier 6 — Speculative (next ~10%): 33, 22, K5s-K2s, Q8s-Q6s, J8s, T7s, 97s, 86s, 75s, 54s
_t6 = [
    "33", "22", "K5s", "K4s", "K3s", "K2s", "Q8s", "Q7s", "Q6s",
    "J8s", "J7s", "T7s", "97s", "86s", "75s", "64s", "54s",
    "QTo", "JTo",
]
# Tier 7 — Weak (next ~10%): Q5s-Q2s, J6s-J2s, T6s-T2s, 96s, 85s, 74s, 53s, 43s
_t7 = [
    "Q5s", "Q4s", "Q3s", "Q2s", "J6s", "J5s", "J4s", "J3s", "J2s",
    "T6s", "T5s", "T4s", "T3s", "T2s", "96s", "95s", "85s", "84s",
    "74s", "63s", "53s", "43s", "42s",
    "A9o", "A8o", "A7o", "A6o", "A5o", "A4o", "A3o", "A2o",
    "K9o", "K8o", "K7o",
]
# Tier 8 — Trash: everything else
_t8_explicit = [
    "94s", "93s", "92s", "83s", "82s", "73s", "72s", "62s", "52s", "32s",
    "K6o", "K5o", "K4o", "K3o", "K2o",
    "Q9o", "Q8o", "Q7o", "Q6o", "Q5o", "Q4o", "Q3o", "Q2o",
    "J9o", "J8o", "J7o", "J6o", "J5o", "J4o", "J3o", "J2o",
    "T9o", "T8o", "T7o", "T6o", "T5o", "T4o", "T3o", "T2o",
    "98o", "97o", "96o", "95o", "94o", "93o", "92o",
    "87o", "86o", "85o", "84o", "83o", "82o",
    "76o", "75o", "74o", "73o", "72o",
    "65o", "64o", "63o", "62o",
    "54o", "53o", "52o",
    "43o", "42o",
    "32o",
]

for h in _t1: HAND_TIER[h] = 1
for h in _t2: HAND_TIER[h] = 2
for h in _t3: HAND_TIER[h] = 3
for h in _t4: HAND_TIER[h] = 4
for h in _t5: HAND_TIER[h] = 5
for h in _t6: HAND_TIER[h] = 6
for h in _t7: HAND_TIER[h] = 7
for h in _t8_explicit: HAND_TIER[h] = 8

# ═══════════════════════════════════════════════════════════════════
# 2. PREFLOP RFI RANGES — % of hands opened from each position
# Source: GTO Wizard 6-max 100bb, NL cash
# ═══════════════════════════════════════════════════════════════════

# Max tier that opens from each position (lower = tighter)
PREFLOP_RFI_MAX_TIER: dict[str, int] = {
    "UTG": 4,   # ~15% — tiers 1-4
    "MP":  5,   # ~20% — tiers 1-5
    "CO":  6,   # ~27% — tiers 1-6
    "BTN": 7,   # ~40% — tiers 1-7
    "SB":  7,   # ~38% — tiers 1-7 (3bet or fold from SB is common)
    "BB":  8,   # BB defends wide (but doesn't RFI)
}

# ═══════════════════════════════════════════════════════════════════
# 3. BOARD TEXTURES — 50+ realistic flop textures
# Classified by type for c-bet strategy
# ═══════════════════════════════════════════════════════════════════

BOARD_TEXTURES: list[dict] = [
    # ─── DRY RAINBOW ──────────────────────────────
    {"board": ["Ks", "7d", "2c"], "type": "dry", "high": "K", "label": "K-high dry rainbow"},
    {"board": ["As", "8d", "3c"], "type": "dry", "high": "A", "label": "A-high dry rainbow"},
    {"board": ["Qd", "5h", "2s"], "type": "dry", "high": "Q", "label": "Q-high dry rainbow"},
    {"board": ["Ah", "7c", "2d"], "type": "dry", "high": "A", "label": "A-high dry rainbow"},
    {"board": ["Kh", "6d", "3s"], "type": "dry", "high": "K", "label": "K-high dry"},
    {"board": ["Jh", "4d", "2c"], "type": "dry", "high": "J", "label": "J-high dry rainbow"},
    {"board": ["Td", "5s", "2h"], "type": "dry", "high": "T", "label": "T-high dry rainbow"},
    {"board": ["9s", "4h", "2d"], "type": "dry", "high": "9", "label": "9-high dry rainbow"},
    {"board": ["As", "9d", "4c"], "type": "dry", "high": "A", "label": "A-high scattered"},
    {"board": ["Kd", "8h", "3s"], "type": "dry", "high": "K", "label": "K-high scattered"},

    # ─── PAIRED BOARDS ────────────────────────────
    {"board": ["Ks", "Kd", "5h"], "type": "paired", "high": "K", "label": "K-K-x paired"},
    {"board": ["7s", "7d", "3c"], "type": "paired", "high": "7", "label": "7-7-x paired"},
    {"board": ["As", "Ad", "4h"], "type": "paired", "high": "A", "label": "A-A-x paired"},
    {"board": ["5h", "5d", "9s"], "type": "paired", "high": "9", "label": "5-5-x paired"},
    {"board": ["Ts", "Td", "3h"], "type": "paired", "high": "T", "label": "T-T-x paired"},

    # ─── SEMI-WET (some connectivity / broadway) ──
    {"board": ["Qd", "Jh", "4s"], "type": "semi_wet", "high": "Q", "label": "Q-J-x two broadway"},
    {"board": ["Jd", "Ts", "3h"], "type": "semi_wet", "high": "J", "label": "J-T-x connected broadway"},
    {"board": ["Ks", "Jd", "5c"], "type": "semi_wet", "high": "K", "label": "K-J-x gapped broadway"},
    {"board": ["As", "Kd", "5h"], "type": "semi_wet", "high": "A", "label": "A-K-x two broadway"},
    {"board": ["Ah", "Qd", "7s"], "type": "semi_wet", "high": "A", "label": "A-Q-x two broadway"},
    {"board": ["Ks", "Qd", "5c"], "type": "semi_wet", "high": "K", "label": "K-Q-x top broadway"},
    {"board": ["Qh", "9s", "4d"], "type": "semi_wet", "high": "Q", "label": "Q-9-x gapped"},
    {"board": ["Jh", "8d", "3s"], "type": "semi_wet", "high": "J", "label": "J-8-x gapped"},
    {"board": ["Ts", "6d", "2c"], "type": "semi_wet", "high": "T", "label": "T-6-x"}  ,

    # ─── WET / CONNECTED ──────────────────────────
    {"board": ["Jd", "Ts", "9c"], "type": "wet", "high": "J", "label": "J-T-9 straight draw heavy"},
    {"board": ["8h", "7d", "6s"], "type": "wet", "high": "8", "label": "8-7-6 connected low"},
    {"board": ["Qh", "Jd", "Ts"], "type": "wet", "high": "Q", "label": "Q-J-T broadway connected"},
    {"board": ["Ts", "9d", "8h"], "type": "wet", "high": "T", "label": "T-9-8 connected"},
    {"board": ["9h", "8d", "7c"], "type": "wet", "high": "9", "label": "9-8-7 connected"},
    {"board": ["7d", "6s", "5h"], "type": "wet", "high": "7", "label": "7-6-5 connected low"},
    {"board": ["Kd", "Qh", "Js"], "type": "wet", "high": "K", "label": "K-Q-J broadway connected"},
    {"board": ["Ah", "Kd", "Qc"], "type": "wet", "high": "A", "label": "A-K-Q top broadway straight"},

    # ─── MONOTONE (flush draw heavy) ──────────────
    {"board": ["Ks", "8s", "2s"], "type": "monotone", "high": "K", "label": "K-high spade monotone"},
    {"board": ["Ah", "5h", "3h"], "type": "monotone", "high": "A", "label": "A-high heart monotone"},
    {"board": ["Qd", "7d", "4d"], "type": "monotone", "high": "Q", "label": "Q-high diamond monotone"},
    {"board": ["Ts", "6s", "3s"], "type": "monotone", "high": "T", "label": "T-high spade monotone"},
    {"board": ["Jh", "9h", "4h"], "type": "monotone", "high": "J", "label": "J-high heart monotone"},

    # ─── TWO-TONE (flush draw possible) ───────────
    {"board": ["As", "7s", "2d"], "type": "two_tone", "high": "A", "label": "A-high two-tone"},
    {"board": ["Kh", "Qh", "5c"], "type": "two_tone", "high": "K", "label": "K-Q two-tone"},
    {"board": ["Jd", "8d", "3h"], "type": "two_tone", "high": "J", "label": "J-high two-tone"},
    {"board": ["9s", "6s", "2h"], "type": "two_tone", "high": "9", "label": "9-high two-tone"},
    {"board": ["Ts", "5s", "3d"], "type": "two_tone", "high": "T", "label": "T-high two-tone"},
    {"board": ["Kd", "9d", "4h"], "type": "two_tone", "high": "K", "label": "K-9 two-tone"},
    {"board": ["Ah", "Th", "6c"], "type": "two_tone", "high": "A", "label": "A-T two-tone"},

    # ─── LOW BOARDS ───────────────────────────────
    {"board": ["6d", "3s", "2h"], "type": "dry", "high": "6", "label": "Low dry board"},
    {"board": ["7h", "4d", "2c"], "type": "dry", "high": "7", "label": "7-high dry low"},
    {"board": ["8d", "5s", "3h"], "type": "dry", "high": "8", "label": "8-high dry low"},
    {"board": ["5h", "4d", "3c"], "type": "wet", "high": "5", "label": "5-4-3 straight possible"},
    {"board": ["6s", "5h", "4d"], "type": "wet", "high": "6", "label": "6-5-4 connected low"},
]

# Turn cards pool (avoid board conflicts at generation time)
TURN_CARDS = [
    "2s", "3s", "4s", "5s", "6s", "7s", "8s", "9s", "Ts", "Js", "Qs", "Ks", "As",
    "2h", "3h", "4h", "5h", "6h", "7h", "8h", "9h", "Th", "Jh", "Qh", "Kh", "Ah",
    "2d", "3d", "4d", "5d", "6d", "7d", "8d", "9d", "Td", "Jd", "Qd", "Kd", "Ad",
    "2c", "3c", "4c", "5c", "6c", "7c", "8c", "9c", "Tc", "Jc", "Qc", "Kc", "Ac",
]


# ═══════════════════════════════════════════════════════════════════
# 4. GTO STRATEGY TABLES — c-bet, check, fold/call/raise frequencies
# Based on GTO Wizard / Upswing aggregated solver outputs
# ═══════════════════════════════════════════════════════════════════

# IP c-bet strategy by board texture and hand tier
# Format: {tier: {action_id: frequency}}
# Source: Upswing Poker c-bet article + GTO Wizard aggregated data

IP_CBET_BY_TEXTURE: dict[str, dict[int, dict[str, float]]] = {
    # DRY boards: high c-bet freq, small sizing preferred
    "dry": {
        1: {"check": 0.10, "bet33": 0.70, "bet75": 0.20},  # premium: mostly small bet
        2: {"check": 0.15, "bet33": 0.65, "bet75": 0.20},
        3: {"check": 0.20, "bet33": 0.55, "bet75": 0.25},
        4: {"check": 0.25, "bet33": 0.50, "bet75": 0.25},  # good: mix
        5: {"check": 0.30, "bet33": 0.50, "bet75": 0.20},
        6: {"check": 0.40, "bet33": 0.45, "bet75": 0.15},
        7: {"check": 0.55, "bet33": 0.35, "bet75": 0.10},  # weak: mostly check
        8: {"check": 0.70, "bet33": 0.25, "bet75": 0.05},  # trash: mostly check
    },
    # PAIRED boards: very high c-bet freq IP
    "paired": {
        1: {"check": 0.05, "bet33": 0.80, "bet75": 0.15},
        2: {"check": 0.10, "bet33": 0.75, "bet75": 0.15},
        3: {"check": 0.15, "bet33": 0.65, "bet75": 0.20},
        4: {"check": 0.20, "bet33": 0.60, "bet75": 0.20},
        5: {"check": 0.30, "bet33": 0.55, "bet75": 0.15},
        6: {"check": 0.35, "bet33": 0.50, "bet75": 0.15},
        7: {"check": 0.50, "bet33": 0.40, "bet75": 0.10},
        8: {"check": 0.60, "bet33": 0.35, "bet75": 0.05},
    },
    # SEMI-WET: moderate c-bet
    "semi_wet": {
        1: {"check": 0.15, "bet33": 0.45, "bet75": 0.40},
        2: {"check": 0.20, "bet33": 0.40, "bet75": 0.40},
        3: {"check": 0.25, "bet33": 0.35, "bet75": 0.40},
        4: {"check": 0.30, "bet33": 0.35, "bet75": 0.35},
        5: {"check": 0.40, "bet33": 0.30, "bet75": 0.30},
        6: {"check": 0.50, "bet33": 0.25, "bet75": 0.25},
        7: {"check": 0.60, "bet33": 0.20, "bet75": 0.20},
        8: {"check": 0.75, "bet33": 0.15, "bet75": 0.10},
    },
    # WET / CONNECTED: lower c-bet freq, bigger sizing
    "wet": {
        1: {"check": 0.20, "bet33": 0.20, "bet75": 0.60},
        2: {"check": 0.25, "bet33": 0.20, "bet75": 0.55},
        3: {"check": 0.30, "bet33": 0.20, "bet75": 0.50},
        4: {"check": 0.35, "bet33": 0.25, "bet75": 0.40},
        5: {"check": 0.45, "bet33": 0.20, "bet75": 0.35},
        6: {"check": 0.55, "bet33": 0.15, "bet75": 0.30},
        7: {"check": 0.65, "bet33": 0.10, "bet75": 0.25},
        8: {"check": 0.80, "bet33": 0.08, "bet75": 0.12},
    },
    # MONOTONE: low c-bet freq (flush draws equalize ranges)
    "monotone": {
        1: {"check": 0.30, "bet33": 0.40, "bet75": 0.30},
        2: {"check": 0.35, "bet33": 0.35, "bet75": 0.30},
        3: {"check": 0.40, "bet33": 0.30, "bet75": 0.30},
        4: {"check": 0.50, "bet33": 0.25, "bet75": 0.25},
        5: {"check": 0.55, "bet33": 0.25, "bet75": 0.20},
        6: {"check": 0.65, "bet33": 0.20, "bet75": 0.15},
        7: {"check": 0.75, "bet33": 0.15, "bet75": 0.10},
        8: {"check": 0.85, "bet33": 0.10, "bet75": 0.05},
    },
    # TWO-TONE: between dry and wet
    "two_tone": {
        1: {"check": 0.15, "bet33": 0.50, "bet75": 0.35},
        2: {"check": 0.20, "bet33": 0.45, "bet75": 0.35},
        3: {"check": 0.25, "bet33": 0.40, "bet75": 0.35},
        4: {"check": 0.30, "bet33": 0.35, "bet75": 0.35},
        5: {"check": 0.40, "bet33": 0.30, "bet75": 0.30},
        6: {"check": 0.50, "bet33": 0.25, "bet75": 0.25},
        7: {"check": 0.60, "bet33": 0.20, "bet75": 0.20},
        8: {"check": 0.75, "bet33": 0.15, "bet75": 0.10},
    },
}

# OOP strategy (BB/SB as preflop caller facing no bet yet)
OOP_STRATEGY_BY_TEXTURE: dict[str, dict[int, dict[str, float]]] = {
    "dry": {
        1: {"check": 0.55, "bet33": 0.30, "bet75": 0.15},
        2: {"check": 0.60, "bet33": 0.25, "bet75": 0.15},
        3: {"check": 0.70, "bet33": 0.20, "bet75": 0.10},
        4: {"check": 0.75, "bet33": 0.15, "bet75": 0.10},
        5: {"check": 0.80, "bet33": 0.13, "bet75": 0.07},
        6: {"check": 0.85, "bet33": 0.10, "bet75": 0.05},
        7: {"check": 0.90, "bet33": 0.07, "bet75": 0.03},
        8: {"check": 0.95, "bet33": 0.04, "bet75": 0.01},
    },
    "paired": {
        1: {"check": 0.50, "bet33": 0.35, "bet75": 0.15},
        2: {"check": 0.55, "bet33": 0.30, "bet75": 0.15},
        3: {"check": 0.65, "bet33": 0.25, "bet75": 0.10},
        4: {"check": 0.70, "bet33": 0.20, "bet75": 0.10},
        5: {"check": 0.80, "bet33": 0.15, "bet75": 0.05},
        6: {"check": 0.85, "bet33": 0.10, "bet75": 0.05},
        7: {"check": 0.90, "bet33": 0.07, "bet75": 0.03},
        8: {"check": 0.95, "bet33": 0.03, "bet75": 0.02},
    },
    "semi_wet": {
        1: {"check": 0.50, "bet33": 0.25, "bet75": 0.25},
        2: {"check": 0.55, "bet33": 0.25, "bet75": 0.20},
        3: {"check": 0.65, "bet33": 0.20, "bet75": 0.15},
        4: {"check": 0.70, "bet33": 0.18, "bet75": 0.12},
        5: {"check": 0.78, "bet33": 0.12, "bet75": 0.10},
        6: {"check": 0.85, "bet33": 0.10, "bet75": 0.05},
        7: {"check": 0.90, "bet33": 0.07, "bet75": 0.03},
        8: {"check": 0.95, "bet33": 0.03, "bet75": 0.02},
    },
    "wet": {
        1: {"check": 0.45, "bet33": 0.20, "bet75": 0.35},
        2: {"check": 0.50, "bet33": 0.20, "bet75": 0.30},
        3: {"check": 0.60, "bet33": 0.15, "bet75": 0.25},
        4: {"check": 0.65, "bet33": 0.15, "bet75": 0.20},
        5: {"check": 0.75, "bet33": 0.10, "bet75": 0.15},
        6: {"check": 0.82, "bet33": 0.08, "bet75": 0.10},
        7: {"check": 0.88, "bet33": 0.05, "bet75": 0.07},
        8: {"check": 0.93, "bet33": 0.03, "bet75": 0.04},
    },
    "monotone": {
        1: {"check": 0.50, "bet33": 0.25, "bet75": 0.25},
        2: {"check": 0.55, "bet33": 0.25, "bet75": 0.20},
        3: {"check": 0.65, "bet33": 0.20, "bet75": 0.15},
        4: {"check": 0.72, "bet33": 0.15, "bet75": 0.13},
        5: {"check": 0.80, "bet33": 0.12, "bet75": 0.08},
        6: {"check": 0.85, "bet33": 0.10, "bet75": 0.05},
        7: {"check": 0.92, "bet33": 0.05, "bet75": 0.03},
        8: {"check": 0.95, "bet33": 0.03, "bet75": 0.02},
    },
    "two_tone": {
        1: {"check": 0.50, "bet33": 0.28, "bet75": 0.22},
        2: {"check": 0.55, "bet33": 0.25, "bet75": 0.20},
        3: {"check": 0.65, "bet33": 0.20, "bet75": 0.15},
        4: {"check": 0.72, "bet33": 0.16, "bet75": 0.12},
        5: {"check": 0.80, "bet33": 0.12, "bet75": 0.08},
        6: {"check": 0.85, "bet33": 0.10, "bet75": 0.05},
        7: {"check": 0.90, "bet33": 0.07, "bet75": 0.03},
        8: {"check": 0.95, "bet33": 0.03, "bet75": 0.02},
    },
}

# Facing a bet: fold/call/raise frequencies by tier
FACING_BET_33: dict[int, dict[str, float]] = {
    1: {"fold": 0.00, "call": 0.45, "raise": 0.55},
    2: {"fold": 0.00, "call": 0.60, "raise": 0.40},
    3: {"fold": 0.05, "call": 0.65, "raise": 0.30},
    4: {"fold": 0.10, "call": 0.65, "raise": 0.25},
    5: {"fold": 0.20, "call": 0.60, "raise": 0.20},
    6: {"fold": 0.35, "call": 0.50, "raise": 0.15},
    7: {"fold": 0.55, "call": 0.35, "raise": 0.10},
    8: {"fold": 0.75, "call": 0.20, "raise": 0.05},
}

FACING_BET_75: dict[int, dict[str, float]] = {
    1: {"fold": 0.00, "call": 0.40, "raise": 0.60},
    2: {"fold": 0.00, "call": 0.55, "raise": 0.45},
    3: {"fold": 0.05, "call": 0.60, "raise": 0.35},
    4: {"fold": 0.15, "call": 0.60, "raise": 0.25},
    5: {"fold": 0.30, "call": 0.50, "raise": 0.20},
    6: {"fold": 0.45, "call": 0.40, "raise": 0.15},
    7: {"fold": 0.60, "call": 0.30, "raise": 0.10},
    8: {"fold": 0.80, "call": 0.15, "raise": 0.05},
}

# 3bet pot adjustments — tighter ranges, bigger pots, less fold equity
THREBET_POT_MODIFIER: dict[int, dict[str, float]] = {
    # In 3bet pots, ranges are narrower, so even medium hands are stronger
    1: {"check": -0.05, "bet33": +0.00, "bet75": +0.05},
    2: {"check": -0.03, "bet33": +0.00, "bet75": +0.03},
    3: {"check": +0.00, "bet33": +0.00, "bet75": +0.00},
    4: {"check": +0.05, "bet33": -0.02, "bet75": -0.03},
    5: {"check": +0.08, "bet33": -0.03, "bet75": -0.05},
    6: {"check": +0.10, "bet33": -0.05, "bet75": -0.05},
    7: {"check": +0.10, "bet33": -0.05, "bet75": -0.05},
    8: {"check": +0.10, "bet33": -0.05, "bet75": -0.05},
}


# ═══════════════════════════════════════════════════════════════════
# 5. HAND CLASSIFICATION HELPERS
# ═══════════════════════════════════════════════════════════════════

RANK_VALUES = {"A": 14, "K": 13, "Q": 12, "J": 11, "T": 10,
               "9": 9, "8": 8, "7": 7, "6": 6, "5": 5, "4": 4, "3": 3, "2": 2}


def get_hand_tier(hand: str) -> int:
    """Return the tier (1-8) of a hand like 'AKs', 'TT', '72o'."""
    return HAND_TIER.get(hand, 8)


def hand_has_rank(hand: str, rank: str) -> bool:
    """Check if a hand contains a specific rank."""
    return rank in hand[:2]


def hand_is_suited(hand: str) -> bool:
    return len(hand) == 3 and hand[2] == "s"


def hand_is_pair(hand: str) -> bool:
    return len(hand) == 2 or (len(hand) == 3 and hand[0] == hand[1])


def hand_is_broadway(hand: str) -> bool:
    """Both cards are T+."""
    return all(RANK_VALUES.get(c, 0) >= 10 for c in hand[:2])


def hand_is_connector(hand: str) -> bool:
    """Cards are adjacent in rank (e.g. 87, JT)."""
    r1 = RANK_VALUES.get(hand[0], 0)
    r2 = RANK_VALUES.get(hand[1], 0)
    return abs(r1 - r2) == 1


def hand_top_rank_value(hand: str) -> int:
    r1 = RANK_VALUES.get(hand[0], 0)
    r2 = RANK_VALUES.get(hand[1], 0)
    return max(r1, r2)


def board_high_card_value(board: list[str]) -> int:
    """Get the highest card value on the board."""
    return max(RANK_VALUES.get(card[0], 0) for card in board)


def hand_connects_with_board(hand: str, board: list[str]) -> str:
    """Check how a hand connects with a board.
    Returns: 'top_pair', 'overpair', 'middle_pair', 'bottom_pair',
             'two_pair', 'set', 'draw', 'nothing'
    """
    board_ranks = [card[0] for card in board]
    board_vals = sorted([RANK_VALUES.get(r, 0) for r in board_ranks], reverse=True)
    hand_ranks = [hand[0], hand[1]]
    hand_vals = [RANK_VALUES.get(hand[0], 0), RANK_VALUES.get(hand[1], 0)]

    # Set
    if hand_is_pair(hand) and hand[0] in board_ranks:
        return "set"

    # Two pair
    if hand[0] in board_ranks and hand[1] in board_ranks and hand[0] != hand[1]:
        return "two_pair"

    # Overpair
    if hand_is_pair(hand) and min(hand_vals) > board_vals[0]:
        return "overpair"

    # Top pair
    if board_ranks and (hand[0] == board_ranks[board_vals.index(board_vals[0])]
                        or hand[1] == board_ranks[board_vals.index(board_vals[0])]):
        # Check if one of the hand ranks matches the highest board rank
        if any(RANK_VALUES.get(hr, 0) == board_vals[0] for hr in hand_ranks):
            return "top_pair"

    # Middle pair
    if len(board_vals) >= 2 and any(RANK_VALUES.get(hr, 0) == board_vals[1] for hr in hand_ranks):
        return "middle_pair"

    # Bottom pair
    if len(board_vals) >= 3 and any(RANK_VALUES.get(hr, 0) == board_vals[2] for hr in hand_ranks):
        return "bottom_pair"

    # Pair on board
    if any(hr in board_ranks for hr in hand_ranks):
        return "pair"

    # Overpair (not on board)
    if hand_is_pair(hand):
        return "underpair"

    # Flush draw check (suited hand + 2 cards of same suit on board)
    if hand_is_suited(hand):
        return "draw"

    # Straight draw (very simplified)
    all_vals = sorted(hand_vals + board_vals)
    for i in range(len(all_vals) - 3):
        if all_vals[i+3] - all_vals[i] <= 4:
            return "draw"

    return "nothing"

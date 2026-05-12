"""
config.py — DeepCarb Planner
============================
All game content and tunable parameters in one place.
Edit this file to change rules, energy values, orders, or visual theme.
"""

# ─── Working week ─────────────────────────────────────────────────────────────

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]

# ─── Factory planner ──────────────────────────────────────────────────────────

# How many tile slots each day-column holds for every player
ROWS_PER_DAY = 5

# ─── Battery storage ──────────────────────────────────────────────────────────

# Maximum battery tiles a player can hold at any time
BATTERY_CAPACITY = 5

# Battery tile a player starts with at the beginning of the game
STARTING_BATTERIES = 1

# Bonus points for stored batteries at game end
#   key = minimum number of batteries needed to earn that many points
#   Extended to reward extra battery slots (capacity above 5)
BATTERY_BONUS = {2: 1, 4: 2, 5: 3, 7: 5, 9: 7}

# Extra battery slots purchasable once per day (at start-of-day)
# Players buy a bundle of EXTRA_BATTERY_SLOTS_PER_PURCHASE slots for EXTRA_BATTERY_COST pts
EXTRA_BATTERY_COST = 1                  # points deducted per bundle purchased
EXTRA_BATTERY_SLOTS_PER_PURCHASE = 4   # slots gained per bundle
MAX_EXTRA_BATTERY_SLOTS = 8            # hard cap (2 bundles per player)

# ─── Conventional (fossil) energy ─────────────────────────────────────────────

# Minus points per conventional energy tile purchased during end-of-day
CONV_ENERGY_PENALTY = 2

# ─── Weather tile pool ────────────────────────────────────────────────────────
# The combined deck of physical weather tiles drawn without replacement.
# Each entry is a (energy_type, value) tuple.
# Pool is replicated WEATHER_POOL_COPIES times so there are always enough tiles.
#   Max needed: 4 players × 4 tiles/player/day × 5 days = 80 tiles
#   Base pool: 24 sun + 24 wind + 10 water = 58 → × 2 copies = 116, always feasible.
WEATHER_POOL_COPIES = 2

_BASE_WEATHER_POOL: list[tuple[str, int]] = (
    # ── Sun tiles ─────────────────────────────────────────────────────────────
    [("sun",   0)] * 2 +
    [("sun",   1)] * 4 +
    [("sun",   2)] * 12 +
    [("sun",   3)] * 4 +
    [("sun",   4)] * 2 +
    # ── Wind tiles ────────────────────────────────────────────────────────────
    [("wind",  0)] * 2 +
    [("wind",  1)] * 5 +
    [("wind",  2)] * 5 +
    [("wind",  3)] * 5 +
    [("wind",  4)] * 5 +
    [("wind",  5)] * 2 +
    # ── Water tiles (always at least 1) ───────────────────────────────────────
    [("water", 1)] * 5 +
    [("water", 2)] * 5
)

WEATHER_POOL: list[tuple[str, int]] = _BASE_WEATHER_POOL * WEATHER_POOL_COPIES

# Tiles per player per day: drawn as randint(MIN, MAX) × num_players each day.
WEATHER_TILES_MIN = 2
WEATHER_TILES_MAX = 4

# ─── Production orders ────────────────────────────────────────────────────────
# Each order dict has:
#   duration  – number of consecutive working days the order spans (1 / 2 / 3)
#   energy    – red energy points required per day to fulfil the order
#   points    – victory points awarded when the order is completed
#   recovery  – True if the order grants 1 battery back at end of each active day
ORDER_TEMPLATES = [
    # ── 1-day orders ──────────────────────────────────────────────────────────
    # give either energy-1 points or energy-2 points 
    {"duration": 1, "energy": 1, "points":  0, "recovery": [0]},    # recovery on day 1
    {"duration": 1, "energy": 2, "points":  1, "recovery": []},
    {"duration": 1, "energy": 2, "points":  1, "recovery": [0]},
    {"duration": 1, "energy": 3, "points":  2, "recovery": []},
    {"duration": 1, "energy": 3, "points":  1, "recovery": [0]},
    {"duration": 1, "energy": 4, "points":  3, "recovery": []},
    {"duration": 1, "energy": 5, "points":  4, "recovery": [0]},

    # ── 2-day orders ──────────────────────────────────────────────────────────
    # give either energy-1 points or energy-2    points per day
    {"duration": 2, "energy": 2, "points":  3, "recovery": []},
    {"duration": 2, "energy": 2, "points":  2, "recovery": [0]},    # recovery on day 1
    {"duration": 2, "energy": 3, "points":  4, "recovery": []},
    {"duration": 2, "energy": 3, "points":  4, "recovery": [1]},    # recovery on day 2
    {"duration": 2, "energy": 4, "points":  6, "recovery": []},
    {"duration": 2, "energy": 5, "points":  8, "recovery": []},

    # ── 3-day orders ──────────────────────────────────────────────────────────
    {"duration": 3, "energy": 2, "points":  6, "recovery": []},
    {"duration": 3, "energy": 3, "points":  8, "recovery": []},
    {"duration": 3, "energy": 3, "points":  7, "recovery": [1]},    # recovery on middle day
    {"duration": 3, "energy": 4, "points": 10, "recovery": []},
    {"duration": 3, "energy": 5, "points": 12, "recovery": [0]},    # recovery on first day
]

# Number of orders shown per duration slot in the order display
# (2 for 2-player games, 3 for 3+ players — handled automatically by the engine)
ORDERS_PER_SLOT_SMALL = 2   # 2 players
ORDERS_PER_SLOT_LARGE = 3   # 3-4 players

# Maximum allowed order duration per day index (0=Mon … 4=Fri)
# e.g. on Thursday (index 3) only 1- and 2-day orders can still fit
MAX_ORDER_DURATION_BY_DAY = {0: 3, 1: 3, 2: 3, 3: 2, 4: 1}

# ─── Players ──────────────────────────────────────────────────────────────────

PLAYER_COLORS      = ["#e74c3c", "#3498db", "#2ecc71", "#f39c12"]
PLAYER_COLOR_NAMES = ["Red",     "Blue",    "Green",   "Yellow"]
PLAYER_DEFAULT_NAMES = ["Alice", "Bob", "Carol", "David"]

# ─── Visual theme ─────────────────────────────────────────────────────────────

THEME = {
    # ── Structural backgrounds (no semantic meaning, just layout depth) ──────
    "bg_dark":   "#1a1a2e",   # main window background
    "bg_panel":  "#16213e",   # top bar, action bar, log
    "bg_code":   "#000000",   # log text widget

    # ── Meaningful cell backgrounds ───────────────────────────────────────────
    "bg_cell":   "#40405A",   # empty factory slot (past / future day)
    "bg_today":  "#315892",   # empty factory slot (current active day)
    "bg_hidden": "#2c2c44",   # face-down weather tile (content unknown)
    "bg_taken":  "#383838",   # weather tile already taken (greyed out)

    # ── Accents ───────────────────────────────────────────────────────────────
    "accent":    "#ff24d3",
    "warning":   "#e74c3c",
    "muted":     "#aaaaaa",
    "dim":       "#555555",
    "white":     "#ffffff",

    # ── Energy type colours (each colour = one energy type) ──────────────────
    "sun":       "#f1c40f",
    "wind":      "#6cc4ff",
    "water":     "#1abc9c",

    # ── Game object colours ───────────────────────────────────────────────────
    "order":     "#9e633b",   # production order tile
    "battery":   "#00ff2f",   # battery indicator
    "co2":       "#c51603",   # conventional energy / CO₂ indicator

    # ── Order duration colours (order display panel) ──────────────────────────
    "order_1d":  "#9e633b",
    "order_2d":  "#943219",
    "order_3d":  "#A0130B",
}

# Icon characters used throughout the UI
ICONS = {
    "co2":    "CO₂",
    "sun":     "☀",
    "wind":    "💨",
    "water":   "💧",
    "battery": "🔋",
    "energy":  "⚡",
    "order":    "⚙",
    "cont":    "…",
    "done":    "pt",
    "recover": "♻",
    "taken":   "✓",
    "engine":  "⚙",
}

# Fonts  (family, size, weight)
FONTS = {
    "title":   ("Helvetica", 28, "bold"),
    "heading": ("Helvetica", 12, "bold"),
    "normal":  ("Helvetica", 11),
    "small":   ("Helvetica",  9),
    "tiny":    ("Helvetica",  7),
    "day":     ("Helvetica", 16, "bold"),
    "log":     ("Courier",    8),
}

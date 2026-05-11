"""
deepcarb_planner.py — DeepCarb Planner
=======================================
Legacy entry point kept for backwards compatibility.
The code has been split into focused modules:

  config.py  — all game content & visual settings (edit this to tweak the game)
  engine.py  — pure game logic (no UI)
  ui.py      — all tkinter UI code

Run the game with:  python deepcarb_planner.py
                or  python run.py
"""

from ui import DeepCarbPlannerApp  # noqa: F401 – re-exported for compatibility

# ─── Game Constants ──────────────────────────────────────────────────────────

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]
ROWS_PER_DAY = 6          # 6 slots per day column in the factory planner
BATTERY_CAPACITY = 5      # max battery tiles in storage
CONV_ENERGY_PENALTY = 2   # minus points per conventional energy tile

# Weather tile pools per type (energy values)
WEATHER_POOLS = {
    "sun":   [0, 1, 1, 2, 2, 2, 3, 3, 3, 4, 4],   # Ø≈2.0, σ≈1.0 + flaute
    "wind":  [0, 1, 1, 2, 2, 3, 3, 4, 4, 4, 5],   # Ø≈2.5, σ≈1.5 + flaute
    "water": [1, 1, 1, 2, 2, 2, 2, 2],            # Ø≈1.5, σ≈0.5, no flaute
}

# Each weather card has a list of tiles with type
WEATHER_CARDS_TEMPLATE = [
    [("sun",3),("wind",3),("sun",2),("wind",2),("water",2)],
    [("wind",4),("sun",3),("wind",3),("sun",1),("water",2)],
    [("sun",4),("wind",4),("sun",2),("water",2),("wind",1)],
    [("wind",5),("sun",3),("wind",2),("sun",2),("water",1)],
    [("sun",3),("wind",3),("water",3),("sun",1),("wind",1)],
]

# Production orders: (energy_needed_per_day, duration_days, points, energy_recovery)
ORDER_TEMPLATES = [
    # 1-day orders
    {"duration": 1, "energy": 2, "points": 3,  "recovery": False},
    {"duration": 1, "energy": 3, "points": 5,  "recovery": False},
    {"duration": 1, "energy": 4, "points": 7,  "recovery": False},
    {"duration": 1, "energy": 1, "points": 1,  "recovery": False},
    {"duration": 1, "energy": 3, "points": 4,  "recovery": True},
    {"duration": 1, "energy": 5, "points": 9,  "recovery": False},
    {"duration": 1, "energy": 2, "points": 2,  "recovery": True},
    # 2-day orders
    {"duration": 2, "energy": 2, "points": 6,  "recovery": False},
    {"duration": 2, "energy": 3, "points": 8,  "recovery": False},
    {"duration": 2, "energy": 4, "points": 11, "recovery": False},
    {"duration": 2, "energy": 2, "points": 5,  "recovery": True},
    {"duration": 2, "energy": 3, "points": 9,  "recovery": True},
    {"duration": 2, "energy": 5, "points": 13, "recovery": False},
    # 3-day orders
    {"duration": 3, "energy": 2, "points": 9,  "recovery": False},
    {"duration": 3, "energy": 3, "points": 12, "recovery": False},
    {"duration": 3, "energy": 4, "points": 16, "recovery": False},
    {"duration": 3, "energy": 3, "points": 11, "recovery": True},
    {"duration": 3, "energy": 5, "points": 18, "recovery": False},
]

PLAYER_COLORS = ["#e74c3c", "#3498db", "#2ecc71", "#f39c12"]
PLAYER_COLOR_NAMES = ["Red", "Blue", "Green", "Yellow"]

# ─── Game State ──────────────────────────────────────────────────────────────

class Player:
    def __init__(self, name, color_idx):
        self.name = name
        self.color = PLAYER_COLORS[color_idx]
        self.color_name = PLAYER_COLOR_NAMES[color_idx]
        # factory_planner[day][row] = tile dict or None
        self.factory_planner = [[None]*ROWS_PER_DAY for _ in range(5)]
        self.battery_storage = 1   # start with 1 battery tile
        self.conventional_energy = 0
        self.priority = color_idx + 1
        self.score = 0

    def energy_in_day(self, day):
        total = 0
        for tile in self.factory_planner[day]:
            if tile and tile["type"] == "energy":
                total += tile["value"]
        return total

    def energy_needed_day(self, day):
        total = 0
        for tile in self.factory_planner[day]:
            if tile and tile["type"] == "order":
                total += tile["energy"]
        return total

    def energy_recovery_day(self, day):
        count = 0
        for tile in self.factory_planner[day]:
            if tile and tile["type"] == "order" and tile.get("recovery"):
                count += 1
        return count

    def free_slots_day(self, day):
        return sum(1 for t in self.factory_planner[day] if t is None)

    def first_free_row(self, day):
        for r, t in enumerate(self.factory_planner[day]):
            if t is None:
                return r
        return None

    def compute_score(self):
        pts = 0
        for day in range(5):
            for tile in self.factory_planner[day]:
                if tile and tile["type"] == "order":
                    pts += tile["points"]
        # battery bonus
        b = self.battery_storage
        if b >= 5:
            pts += 3
        elif b >= 4:
            pts += 2
        elif b >= 2:
            pts += 1
        # conventional energy penalty
        pts -= self.conventional_energy * CONV_ENERGY_PENALTY
        return pts


class WeatherCard:
    """Represents one day's weather card with tiles (face-up or face-down)."""
    def __init__(self, tiles):
        # tiles = list of {"type": "sun"/"wind"/"water", "value": int, "revealed": bool}
        self.tiles = tiles

    def unrevealed_tiles(self):
        return [t for t in self.tiles if not t["revealed"]]

    def available_tiles(self):
        """All tiles still on card (not yet taken by any player), including unrevealed."""
        return [t for t in self.tiles if t.get("on_card", True)]

    def revealed_available(self):
        return [t for t in self.tiles if t["revealed"] and t.get("on_card", True)]

    def unrevealed_available(self):
        return [t for t in self.tiles if not t["revealed"] and t.get("on_card", True)]

    def has_positive_energy(self):
        """True if any tile with value > 0 is still on the card."""
        return any(t["value"] > 0 and t.get("on_card", True) for t in self.tiles)


def make_weather_card(day_idx):
    template = WEATHER_CARDS_TEMPLATE[day_idx]
    tiles = []
    for etype, _ in template:
        pool = WEATHER_POOLS[etype][:]
        random.shuffle(pool)
        val = pool[0]
        tiles.append({"type": etype, "value": val, "revealed": False, "on_card": True})
    # Reveal only the first tile
    if tiles:
        tiles[0]["revealed"] = True
    return WeatherCard(tiles)


def make_order_deck():
    deck = copy.deepcopy(ORDER_TEMPLATES)
    random.shuffle(deck)
    return deck


# ─── Game Engine ─────────────────────────────────────────────────────────────

class GameEngine:
    def __init__(self, player_names):
        self.players = [Player(n, i) for i, n in enumerate(player_names)]
        self.num_players = len(player_names)
        self.current_day = 0         # 0=Mon ... 4=Fri
        self.current_player_idx = 0
        self.turn_order = list(range(self.num_players))  # indices in play order
        self.weather_cards = [make_weather_card(d) for d in range(5)]
        self.order_deck = make_order_deck()
        self.order_display = []      # visible orders in the display
        self._fill_order_display()
        self.phase = "work"          # "work" | "end_of_day"
        self.action_state = "reveal" # "reveal" | "action" | "done"
        self.day_ended = False
        self.game_over = False
        self.log_messages = []

    def _fill_order_display(self):
        """Fill order display: 2 of each size (1,2,3), or 3 for >=3 players."""
        per_size = 3 if self.num_players >= 3 else 2
        max_day = self.current_day
        available_durations = [1, 2, 3]
        if max_day >= 3:  # Thu: no 3-day orders
            available_durations = [1, 2]
        if max_day >= 4:  # Fri: only 1-day
            available_durations = [1]

        self.order_display = []
        for dur in available_durations:
            count = 0
            for o in self.order_deck[:]:
                if o["duration"] == dur and count < per_size:
                    self.order_display.append(o)
                    self.order_deck.remove(o)
                    count += 1

    def refresh_order_display(self):
        """Put current display back and draw fresh ones."""
        self.order_deck.extend(self.order_display)
        random.shuffle(self.order_deck)
        self.order_display = []
        self._fill_order_display()

    def current_player(self):
        return self.players[self.turn_order[self.current_player_idx]]

    def weather_card(self):
        return self.weather_cards[self.current_day]

    def log(self, msg):
        self.log_messages.append(msg)
        if len(self.log_messages) > 100:
            self.log_messages = self.log_messages[-100:]

    def do_reveal_tile(self, tile):
        """Reveal a weather tile (mandatory first action)."""
        tile["revealed"] = True
        self.log(f"{self.current_player().name} reveals a {tile['type']} tile: {tile['value']} energy")
        self.action_state = "action"

    def do_buy_energy(self, tile):
        """Take an energy tile from the weather card and place in current day."""
        player = self.current_player()
        day = self.current_day
        if player.free_slots_day(day) == 0:
            self.log("No free slots today!")
            return False
        tile["on_card"] = False
        row = player.first_free_row(day)
        player.factory_planner[day][row] = {
            "type": "energy",
            "energy_type": tile["type"],
            "value": tile["value"],
        }
        self.log(f"{player.name} buys {tile['type']} energy: +{tile['value']}")
        self._check_day_end_trigger(tile)
        self._advance_turn()
        return True

    def do_take_order(self, order, start_day):
        """Place an order starting at start_day."""
        player = self.current_player()
        dur = order["duration"]
        # Check enough free slots in each required day
        for d in range(start_day, start_day + dur):
            if d >= 5 or player.free_slots_day(d) == 0:
                self.log(f"Not enough space for this order!")
                return False
        # Place order tile in each day column
        for d in range(start_day, start_day + dur):
            row = player.first_free_row(d)
            player.factory_planner[d][row] = {
                "type": "order",
                "duration": dur,
                "energy": order["energy"],
                "points": order["points"],
                "recovery": order.get("recovery", False),
                "start_day": start_day,
                "day_offset": d - start_day,
                "total_days": dur,
            }
        if order in self.order_display:
            self.order_display.remove(order)
        self.log(f"{player.name} takes a {dur}-day order ({order['energy']} energy/day, {order['points']} pts)")
        self._advance_turn()
        return True

    def do_pass(self):
        player = self.current_player()
        self.log(f"{player.name} passes")
        self._advance_turn()

    def _check_day_end_trigger(self, taken_tile):
        wc = self.weather_card()
        if not wc.has_positive_energy():
            self.log("Last positive energy tile taken — end of work day triggered!")
            self.day_ended = True

    def _advance_turn(self):
        self.action_state = "reveal"
        wc = self.weather_card()
        # If day ended: everyone gets one last action (order only)
        # Simple model: just move to next player
        self.current_player_idx = (self.current_player_idx + 1) % self.num_players
        if self.day_ended:
            # Check if we've gone around once after end trigger
            if self.current_player_idx == 0:
                self._end_of_day()

    def _end_of_day(self):
        self.log(f"=== End of {DAYS[self.current_day]} ===")
        for player in self.players:
            self._resolve_energy_balance(player)
        self.refresh_order_display()
        self.current_day += 1
        if self.current_day >= 5:
            self._end_game()
        else:
            self.day_ended = False
            self.current_player_idx = 0
            self._assign_priorities()
            self.log(f"=== Start of {DAYS[self.current_day]} ===")

    def _resolve_energy_balance(self, player):
        day = self.current_day
        available = player.energy_in_day(day)
        needed = player.energy_needed_day(day)
        balance = available - needed
        recovery = player.energy_recovery_day(day)

        if balance >= 0:
            # Store surplus
            surplus = balance
            stored = min(surplus, BATTERY_CAPACITY - player.battery_storage)
            player.battery_storage += stored
            self.log(f"{player.name}: +{surplus} energy balance, stored {stored} batteries")
        else:
            deficit = -balance
            # Use batteries first
            use_batteries = min(deficit, player.battery_storage)
            player.battery_storage -= use_batteries
            deficit -= use_batteries
            if deficit > 0:
                # Buy conventional energy
                player.conventional_energy += deficit
                self.log(f"{player.name}: bought {deficit} conventional energy (-{deficit*CONV_ENERGY_PENALTY} pts)")
            else:
                self.log(f"{player.name}: used {use_batteries} batteries to cover deficit")

        # Energy recovery from orders
        if recovery > 0:
            store_rec = min(recovery, BATTERY_CAPACITY - player.battery_storage)
            player.battery_storage += store_rec
            self.log(f"{player.name}: recovered {store_rec} energy from orders")

    def _assign_priorities(self):
        # Assign priorities based on energy need in new day
        day = self.current_day
        needs = [(p.energy_needed_day(day), i) for i, p in enumerate(self.players)]
        needs.sort(key=lambda x: -x[0])
        self.turn_order = [idx for _, idx in needs]
        self.current_player_idx = 0
        self.log(f"Turn order for {DAYS[day]}: {[self.players[i].name for i in self.turn_order]}")

    def _end_game(self):
        self.game_over = True
        self.log("=== GAME OVER ===")
        for p in self.players:
            p.score = p.compute_score()
            self.log(f"{p.name}: {p.score} points")

    def force_end_of_day(self):
        """Allow manual end-of-day trigger."""
        self.day_ended = True
        self._end_of_day()


# ─── Tkinter UI ──────────────────────────────────────────────────────────────

class DeepCarbPlannerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("DeepCarb Planner")
        self.configure(bg="#1a1a2e")
        self.resizable(True, True)
        self.engine = None
        self._build_start_screen()

    # ── Start screen ────────────────────────────────────────────────────────

    def _build_start_screen(self):
        self._clear_window()
        frame = tk.Frame(self, bg="#1a1a2e", padx=40, pady=40)
        frame.pack(expand=True)

        tk.Label(frame, text="DeepCarb Planner", font=("Helvetica", 28, "bold"),
                 fg="#00d4aa", bg="#1a1a2e").pack(pady=(0, 8))
        tk.Label(frame, text="SenetFF / HTWG  –  Energy Planning Game",
                 font=("Helvetica", 11), fg="#aaa", bg="#1a1a2e").pack(pady=(0, 30))

        tk.Label(frame, text="Number of players:", font=("Helvetica", 13),
                 fg="white", bg="#1a1a2e").pack()
        self.num_players_var = tk.IntVar(value=2)
        spinbox = tk.Spinbox(frame, from_=2, to=4, textvariable=self.num_players_var,
                             font=("Helvetica", 13), width=4, justify="center")
        spinbox.pack(pady=6)

        self.name_entries = []
        self.name_frame = tk.Frame(frame, bg="#1a1a2e")
        self.name_frame.pack(pady=10)
        self.num_players_var.trace_add("write", lambda *a: self._update_name_entries())
        self._update_name_entries()

        tk.Button(frame, text="Start Game", font=("Helvetica", 14, "bold"),
                  bg="#00d4aa", fg="#1a1a2e", padx=20, pady=8,
                  relief="flat", cursor="hand2",
                  command=self._start_game).pack(pady=20)

        tk.Label(frame, text="5 working days  |  Collect energy  |  Fulfill orders  |  Maximize points",
                 font=("Helvetica", 9), fg="#666", bg="#1a1a2e").pack()

    def _update_name_entries(self):
        for w in self.name_frame.winfo_children():
            w.destroy()
        self.name_entries = []
        n = self.num_players_var.get()
        defaults = ["Alice", "Bob", "Carol", "David"]
        for i in range(n):
            row = tk.Frame(self.name_frame, bg="#1a1a2e")
            row.pack(pady=3)
            tk.Label(row, text=f"Player {i+1} ({PLAYER_COLOR_NAMES[i]}):",
                     font=("Helvetica", 11), fg=PLAYER_COLORS[i], bg="#1a1a2e",
                     width=20, anchor="e").pack(side="left")
            e = tk.Entry(row, font=("Helvetica", 11), width=14)
            e.insert(0, defaults[i])
            e.pack(side="left", padx=6)
            self.name_entries.append(e)

    def _start_game(self):
        names = [e.get().strip() or f"Player {i+1}" for i, e in enumerate(self.name_entries)]
        self.engine = GameEngine(names)
        self._build_game_screen()

    # ── Main game screen ─────────────────────────────────────────────────────

    def _build_game_screen(self):
        self._clear_window()
        self.geometry("1200x800")

        # Top bar
        top = tk.Frame(self, bg="#16213e", pady=6)
        top.pack(fill="x")
        self.day_label = tk.Label(top, text="", font=("Helvetica", 16, "bold"),
                                  fg="#00d4aa", bg="#16213e")
        self.day_label.pack(side="left", padx=20)
        self.turn_label = tk.Label(top, text="", font=("Helvetica", 12),
                                   fg="white", bg="#16213e")
        self.turn_label.pack(side="left", padx=10)
        tk.Button(top, text="End Day", font=("Helvetica", 10, "bold"),
                  bg="#e74c3c", fg="white", relief="flat", padx=10,
                  cursor="hand2", command=self._force_end_day).pack(side="right", padx=10)
        tk.Button(top, text="Rules", font=("Helvetica", 10),
                  bg="#555", fg="white", relief="flat", padx=10,
                  cursor="hand2", command=self._show_rules).pack(side="right", padx=4)

        # Main area
        main = tk.Frame(self, bg="#1a1a2e")
        main.pack(fill="both", expand=True)

        # Left: weather + orders
        left = tk.Frame(main, bg="#1a1a2e", width=280)
        left.pack(side="left", fill="y", padx=10, pady=10)
        left.pack_propagate(False)

        tk.Label(left, text="Weather Card", font=("Helvetica", 12, "bold"),
                 fg="#f39c12", bg="#1a1a2e").pack()
        self.weather_frame = tk.Frame(left, bg="#1a1a2e")
        self.weather_frame.pack(fill="x", pady=4)

        tk.Label(left, text="Production Orders", font=("Helvetica", 12, "bold"),
                 fg="#9b59b6", bg="#1a1a2e").pack(pady=(12, 0))
        self.orders_frame = tk.Frame(left, bg="#1a1a2e")
        self.orders_frame.pack(fill="x", pady=4)

        # Center: factory planners (scrollable)
        center = tk.Frame(main, bg="#1a1a2e")
        center.pack(side="left", fill="both", expand=True, padx=6, pady=10)

        tk.Label(center, text="Factory Planners", font=("Helvetica", 12, "bold"),
                 fg="#00d4aa", bg="#1a1a2e").pack()

        canvas = tk.Canvas(center, bg="#1a1a2e", highlightthickness=0)
        vsb = ttk.Scrollbar(center, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        self.factory_inner = tk.Frame(canvas, bg="#1a1a2e")
        self.factory_win_id = canvas.create_window((0, 0), window=self.factory_inner, anchor="nw")
        self.factory_inner.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        # Right: log
        right = tk.Frame(main, bg="#1a1a2e", width=220)
        right.pack(side="right", fill="y", padx=10, pady=10)
        right.pack_propagate(False)

        tk.Label(right, text="Game Log", font=("Helvetica", 11, "bold"),
                 fg="#aaa", bg="#1a1a2e").pack()
        self.log_text = tk.Text(right, font=("Courier", 8), bg="#0d1117",
                                fg="#ccc", wrap="word", state="disabled",
                                relief="flat", height=40)
        self.log_text.pack(fill="both", expand=True, pady=4)

        # Action area at bottom
        self.action_frame = tk.Frame(self, bg="#16213e", pady=8)
        self.action_frame.pack(fill="x", padx=10, pady=(0, 6))

        self._refresh_ui()

    # ── UI Refresh ───────────────────────────────────────────────────────────

    def _refresh_ui(self):
        if self.engine.game_over:
            self._show_end_screen()
            return
        eng = self.engine
        player = eng.current_player()
        day_name = DAYS[eng.current_day]

        self.day_label.config(text=f"Day: {day_name}")
        self.turn_label.config(
            text=f"Current: {player.name}  |  Action: {'Reveal a tile' if eng.action_state == 'reveal' else 'Buy energy / Take order / Pass'}"
        )

        self._draw_weather_card()
        self._draw_orders()
        self._draw_factory_planners()
        self._draw_action_buttons()
        self._update_log()

    def _draw_weather_card(self):
        for w in self.weather_frame.winfo_children():
            w.destroy()
        wc = self.engine.weather_card()
        type_colors = {"sun": "#f1c40f", "wind": "#3498db", "water": "#1abc9c"}
        type_icons  = {"sun": "☀", "wind": "💨", "water": "💧"}
        for i, tile in enumerate(wc.tiles):
            on = tile.get("on_card", True)
            color = type_colors.get(tile["type"], "#888")
            if not on:
                bg, text, fg = "#333", "✓ taken", "#555"
            elif tile["revealed"]:
                bg = color
                text = f"{type_icons[tile['type']]}  {tile['value']}"
                fg = "#1a1a2e"
            else:
                bg = "#334"
                text = f"{type_icons[tile['type']]}  ?"
                fg = "#aaa"

            btn = tk.Button(
                self.weather_frame,
                text=text, font=("Helvetica", 11, "bold"),
                bg=bg, fg=fg, relief="flat", padx=8, pady=6,
                state="normal" if on and not self.engine.game_over else "disabled",
                cursor="hand2" if on else "arrow",
                command=lambda t=tile: self._on_weather_tile_click(t)
            )
            btn.pack(fill="x", pady=2)

    def _draw_orders(self):
        for w in self.orders_frame.winfo_children():
            w.destroy()
        dur_colors = {1: "#8e44ad", 2: "#2980b9", 3: "#16a085"}
        for order in self.engine.order_display:
            dur = order["duration"]
            rec = " ♻" if order.get("recovery") else ""
            text = f"[{dur}d] ⚡{order['energy']}/day  +{order['points']}pts{rec}"
            btn = tk.Button(
                self.orders_frame,
                text=text, font=("Helvetica", 9, "bold"),
                bg=dur_colors.get(dur, "#555"), fg="white",
                relief="flat", padx=6, pady=5,
                cursor="hand2",
                command=lambda o=order: self._on_order_click(o)
            )
            btn.pack(fill="x", pady=2)
        if not self.engine.order_display:
            tk.Label(self.orders_frame, text="No orders available",
                     font=("Helvetica", 9), fg="#666", bg="#1a1a2e").pack()

    def _draw_factory_planners(self):
        for w in self.factory_inner.winfo_children():
            w.destroy()
        eng = self.engine
        cell_w, cell_h = 56, 32

        # Header row: day labels
        header = tk.Frame(self.factory_inner, bg="#1a1a2e")
        header.pack(fill="x", pady=(4, 0))
        tk.Label(header, text="Player", font=("Helvetica", 9, "bold"),
                 fg="#aaa", bg="#1a1a2e", width=10).grid(row=0, column=0)
        for d, day in enumerate(DAYS):
            color = "#00d4aa" if d == eng.current_day else "#666"
            tk.Label(header, text=day, font=("Helvetica", 9, "bold"),
                     fg=color, bg="#1a1a2e", width=8).grid(row=0, column=d+1)
        tk.Label(header, text="🔋", font=("Helvetica", 9),
                 fg="#f39c12", bg="#1a1a2e", width=4).grid(row=0, column=6)
        tk.Label(header, text="CO₂", font=("Helvetica", 9),
                 fg="#e74c3c", bg="#1a1a2e", width=4).grid(row=0, column=7)

        # Player rows
        type_colors = {"sun": "#f1c40f", "wind": "#3498db", "water": "#1abc9c",
                       "conventional": "#888"}
        for pi, player in enumerate(eng.players):
            pframe = tk.Frame(self.factory_inner, bg="#1a1a2e",
                              highlightbackground=player.color,
                              highlightthickness=2)
            pframe.pack(fill="x", padx=4, pady=3)

            tk.Label(pframe, text=player.name, font=("Helvetica", 9, "bold"),
                     fg=player.color, bg="#1a1a2e", width=10).grid(
                         row=0, column=0, rowspan=ROWS_PER_DAY, sticky="nsew")

            for d in range(5):
                for r in range(ROWS_PER_DAY):
                    tile = player.factory_planner[d][r]
                    if tile is None:
                        bg = "#16213e" if d == eng.current_day else "#111"
                        text = ""
                    elif tile["type"] == "energy":
                        ec = type_colors.get(tile["energy_type"], "#aaa")
                        bg = ec
                        icons = {"sun": "☀", "wind": "💨", "water": "💧"}
                        text = f"{icons.get(tile['energy_type'],'')} {tile['value']}"
                    elif tile["type"] == "order":
                        bg = "#5d4e99"
                        day_off = tile.get("day_offset", 0)
                        total = tile.get("total_days", 1)
                        rec = "♻" if tile.get("recovery") else ""
                        if day_off == 0:
                            text = f"▶{tile['energy']}⚡{rec}"
                        elif day_off == total - 1:
                            text = f"{tile['points']}pt{rec}"
                        else:
                            text = f"…{tile['energy']}⚡{rec}"
                    else:
                        bg = "#333"
                        text = ""

                    lbl = tk.Label(pframe, text=text, font=("Helvetica", 7),
                                   bg=bg, fg="#1a1a2e" if bg not in ("#111","#16213e","#333","#5d4e99") else "white",
                                   width=7, height=1, relief="solid",
                                   bd=0, padx=1)
                    lbl.grid(row=r, column=d+1, padx=1, pady=1, sticky="nsew")

            # Battery and CO2
            tk.Label(pframe, text=f"{player.battery_storage}/{BATTERY_CAPACITY}",
                     font=("Helvetica", 9, "bold"), fg="#f39c12", bg="#1a1a2e",
                     width=4).grid(row=0, column=6, rowspan=ROWS_PER_DAY)
            tk.Label(pframe, text=f"{player.conventional_energy}",
                     font=("Helvetica", 9, "bold"), fg="#e74c3c", bg="#1a1a2e",
                     width=4).grid(row=0, column=7, rowspan=ROWS_PER_DAY)

    def _draw_action_buttons(self):
        for w in self.action_frame.winfo_children():
            w.destroy()
        eng = self.engine
        player = eng.current_player()

        tk.Label(self.action_frame,
                 text=f"{player.name}'s turn  —  ",
                 font=("Helvetica", 10, "bold"),
                 fg=player.color, bg="#16213e").pack(side="left", padx=8)

        if eng.action_state == "action":
            tk.Button(self.action_frame, text="Pass (skip action)",
                      font=("Helvetica", 10), bg="#555", fg="white",
                      relief="flat", padx=10, pady=4, cursor="hand2",
                      command=self._on_pass).pack(side="left", padx=6)

        info = f"Battery: {player.battery_storage}/{BATTERY_CAPACITY}  |  "
        info += f"CO₂ tiles: {player.conventional_energy}  |  "
        info += f"Today's energy: {player.energy_in_day(eng.current_day)} ⚡  |  "
        info += f"Today's need: {player.energy_needed_day(eng.current_day)} ⚡"
        tk.Label(self.action_frame, text=info,
                 font=("Helvetica", 9), fg="#aaa", bg="#16213e").pack(side="left", padx=14)

    def _update_log(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        for msg in self.engine.log_messages[-60:]:
            self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    # ── Interactions ─────────────────────────────────────────────────────────

    def _on_weather_tile_click(self, tile):
        eng = self.engine
        if eng.game_over:
            return
        if not tile.get("on_card", True):
            return
        if eng.action_state == "reveal":
            eng.do_reveal_tile(tile)
            self._refresh_ui()
        elif eng.action_state == "action":
            # Buying energy: place tile in factory
            player = eng.current_player()
            if player.free_slots_day(eng.current_day) == 0:
                messagebox.showwarning("No space", "Your factory is full for today!")
                return
            eng.do_buy_energy(tile)
            if eng.game_over:
                self._show_end_screen()
            elif eng.day_ended and eng.current_day >= 5:
                self._show_end_screen()
            else:
                self._refresh_ui()
        else:
            messagebox.showinfo("Info", "Please reveal a tile first.")

    def _on_order_click(self, order):
        eng = self.engine
        if eng.game_over:
            return
        if eng.action_state == "reveal":
            messagebox.showinfo("Reveal first", "You must reveal a weather tile before taking an order.")
            return
        player = eng.current_player()
        dur = order["duration"]
        # Determine allowed start days
        allowed = []
        for d in range(eng.current_day, 5 - dur + 1):
            ok = True
            for dd in range(d, d + dur):
                if player.free_slots_day(dd) == 0:
                    ok = False
                    break
            if ok:
                allowed.append(d)
        if not allowed:
            messagebox.showwarning("No space", "No room in your factory for this order!")
            return
        if len(allowed) == 1:
            start = allowed[0]
        else:
            # Ask user which start day
            win = tk.Toplevel(self)
            win.title("Choose start day")
            win.configure(bg="#1a1a2e")
            win.grab_set()
            tk.Label(win, text=f"Start this {dur}-day order on:",
                     font=("Helvetica", 11), fg="white", bg="#1a1a2e").pack(pady=10, padx=20)
            chosen = tk.IntVar(value=allowed[0])
            for d in allowed:
                tk.Radiobutton(win, text=DAYS[d], variable=chosen, value=d,
                               font=("Helvetica", 11), fg="#00d4aa", bg="#1a1a2e",
                               selectcolor="#333", activebackground="#1a1a2e").pack(pady=2)
            result = [None]
            def confirm():
                result[0] = chosen.get()
                win.destroy()
            tk.Button(win, text="Place Order", bg="#00d4aa", fg="#1a1a2e",
                      font=("Helvetica", 11, "bold"), relief="flat", padx=12,
                      command=confirm).pack(pady=10)
            self.wait_window(win)
            if result[0] is None:
                return
            start = result[0]

        eng.do_take_order(order, start)
        if eng.game_over:
            self._show_end_screen()
        else:
            self._refresh_ui()

    def _on_pass(self):
        self.engine.do_pass()
        self._refresh_ui()

    def _force_end_day(self):
        if messagebox.askyesno("End Day", f"Force end of {DAYS[self.engine.current_day]}?"):
            self.engine.force_end_of_day()
            if self.engine.game_over:
                self._show_end_screen()
            else:
                self._refresh_ui()

    # ── End Screen ───────────────────────────────────────────────────────────

    def _show_end_screen(self):
        self._clear_window()
        frame = tk.Frame(self, bg="#1a1a2e", padx=40, pady=40)
        frame.pack(expand=True)

        tk.Label(frame, text="Game Over!", font=("Helvetica", 28, "bold"),
                 fg="#00d4aa", bg="#1a1a2e").pack(pady=(0, 20))

        players_sorted = sorted(self.engine.players, key=lambda p: -p.compute_score())
        for rank, p in enumerate(players_sorted):
            s = p.compute_score()
            orders_pts = sum(
                t["points"] for day in p.factory_planner for t in day
                if t and t["type"] == "order" and t.get("day_offset", 0) == t.get("total_days", 1) - 1
            )
            batt_b = 1 if p.battery_storage >= 2 else 0
            row = tk.Frame(frame, bg="#16213e", pady=8, padx=20)
            row.pack(fill="x", pady=4)
            medal = ["🥇", "🥈", "🥉", "  "][min(rank, 3)]
            tk.Label(row, text=f"{medal}  {p.name}", font=("Helvetica", 14, "bold"),
                     fg=p.color, bg="#16213e", width=18, anchor="w").pack(side="left")
            tk.Label(row, text=f"{s} pts",
                     font=("Helvetica", 14, "bold"), fg="white", bg="#16213e").pack(side="right")
            detail = f"CO₂: -{p.conventional_energy * CONV_ENERGY_PENALTY}  Battery: {p.battery_storage}🔋"
            tk.Label(row, text=detail, font=("Helvetica", 9), fg="#aaa", bg="#16213e").pack(side="right", padx=20)

        tk.Button(frame, text="Play Again", font=("Helvetica", 13, "bold"),
                  bg="#00d4aa", fg="#1a1a2e", padx=20, pady=8, relief="flat",
                  cursor="hand2", command=self._build_start_screen).pack(pady=30)

    # ── Rules Popup ──────────────────────────────────────────────────────────

    def _show_rules(self):
        win = tk.Toplevel(self)
        win.title("Rules Summary — DeepCarb Planner")
        win.configure(bg="#1a1a2e")
        win.geometry("600x520")
        text = tk.Text(win, font=("Helvetica", 9), bg="#0d1117", fg="#ccc",
                       wrap="word", padx=12, pady=10, relief="flat")
        text.pack(fill="both", expand=True)
        rules = """\
DEEPCARB PLANNER — Rules Summary
=================================

GOAL
Earn the most points by fulfilling production orders using renewable energy.

SETUP (per player)
• 1 factory planner (5 days × 6 slots)
• 1 battery tile in storage (max 5)
• Priority tokens 1-4 decide turn order

EACH DAY (Mon–Fri)
I. Assign priorities based on energy need in this day's column (highest = first).

II. Work Phase (repeat until day ends):
  On your turn you do TWO actions:
  1. REVEAL: flip one weather tile on today's card (mandatory).
  2. CHOOSE one of:
     A) BUY ENERGY — take any tile from today's weather card,
        place face-up in any free slot of today's column.
     B) TAKE ORDER — take an order from the display,
        place it horizontally in free slots (current or future days only).
     C) PASS — skip the second action.

  Day ends when: all positive energy tiles are taken, OR everyone passes.

III. End of Day — Energy Balance:
  needed = sum of red ⚡ on orders in today's column
  available = sum of yellow ⚡ on energy tiles in today's column
  balance = available − needed

  • Surplus → store as battery tiles (max 5 total)
  • Deficit → use batteries first, then buy conventional energy (−2 pts each)
  • Orders with ♻ symbol → gain 1 battery per symbol (if storage not full)

ENERGY TYPES
  ☀ Sun:   avg 2, σ 1  (may show 0 = cloud)
  💨 Wind:  avg 2.5, σ 1.5  (may show 0 = calm)
  💧 Water: avg 1.5, σ 0.5  (no zero tiles)

ORDERS
  Duration 1/2/3 days. Must be placed in consecutive future day columns.
  Energy needed per day shown in red. Points shown on order tile.
  3-day orders not available Thu/Fri. 2-day orders not available Fri.

SCORING (end of Friday)
  + Points on completed orders
  + Battery bonus: 2=1pt, 4=2pts, 5=3pts
  − Conventional energy: 2 pts per tile
"""
        text.insert("end", rules)
        text.config(state="disabled")

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _clear_window(self):
        for w in self.winfo_children():
            w.destroy()


# ─── Entry point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = DeepCarbPlannerApp()
    app.mainloop()

"""
ui.py — DeepCarb Planner
=========================
All tkinter UI code.  Imports game logic from engine.py and
visual settings from config.py.  No game rules live here.
"""

import tkinter as tk
from tkinter import ttk, messagebox

from config import (
    DAYS, ROWS_PER_DAY, BATTERY_CAPACITY, CONV_ENERGY_PENALTY,
    EXTRA_BATTERY_COST, MAX_EXTRA_BATTERY_SLOTS, EXTRA_BATTERY_SLOTS_PER_PURCHASE,
    BATTERY_BONUS,
    PLAYER_COLORS, PLAYER_COLOR_NAMES, PLAYER_DEFAULT_NAMES,
    THEME, ICONS, FONTS,
)
from engine import GameEngine, Player

day_column_width = 10


# ─── Reusable helpers ─────────────────────────────────────────────────────────

def _styled_button(parent, text: str, color: str, command, font=None, **kw) -> tk.Button:
    """A flat button with the given background colour."""
    return tk.Button(
        parent, text=text, bg=color, fg=THEME["bg_dark"],
        font=font or FONTS["normal"], relief="flat", cursor="hand2",
        command=command, **kw,
    )


def _label(parent, text: str, font_key="normal", fg=None, **kw) -> tk.Label:
    return tk.Label(
        parent, text=text,
        font=FONTS[font_key],
        fg=fg or THEME["muted"],
        bg=THEME["bg_dark"],
        **kw,
    )


def _signed(n: int) -> str:
    """Return a number with an explicit +/− sign."""
    return f"+{n}" if n >= 0 else str(n)


def _dim_color(hex_color: str, factor: float) -> str:
    """Return hex_color darkened by factor (0=black, 1=original)."""
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    return f"#{int(r*factor):02x}{int(g*factor):02x}{int(b*factor):02x}"


_DUR_COLOR = {
    1: None,   # filled after module load — see bottom of file
    2: None,
    3: None,
}


def _dur_color(dur: int) -> str:
    return {
        1: THEME["order_1d"],
        2: THEME["order_2d"],
        3: THEME["order_3d"],
    }.get(dur, "#555")


_BONUS_GREEN = "#1e7b1e"   # dark green — readable on both bright-green fill and dark empty


def _battery_canvas(
    parent,
    stored: int,
    capacity: int,
    w: int = 28,
    h: int = 80,
    bonus_map: dict | None = None,
) -> tk.Canvas:
    """Draw a vertical segmented battery; filled segments = stored (bottom to top).
    bonus_map: {segment_index_from_bottom: label_str} — label drawn inside that segment.
    """
    SEG_GAP = 2
    CAP_H   = 6
    BORDER  = 2
    GREEN   = THEME["battery"]
    EMPTY   = THEME["bg_cell"]
    BG      = THEME["bg_dark"]

    c = tk.Canvas(parent, width=w, height=h, bg=BG, highlightthickness=0)
    segs = max(capacity, 1)
    body_h  = h - CAP_H - BORDER
    seg_h   = max(3, (body_h - SEG_GAP * (segs - 1)) // segs)
    cx      = w // 2

    # Terminal cap
    c.create_rectangle(cx - (w - 4) // 4, 0, cx + (w - 4) // 4, CAP_H,
                       fill=GREEN, outline="")
    # Body outline
    body_y1 = CAP_H + BORDER + segs * seg_h + SEG_GAP * (segs - 1) + BORDER
    c.create_rectangle(BORDER, CAP_H, w - BORDER, body_y1,
                       outline=GREEN, fill=BG, width=BORDER)
    # Segments bottom-to-top
    for i in range(segs):
        y1 = body_y1 - BORDER - i * (seg_h + SEG_GAP)
        y0 = y1 - seg_h
        c.create_rectangle(BORDER * 2, y0, w - BORDER * 2, y1,
                           fill=GREEN if i < stored else EMPTY, outline="")
        if bonus_map and i in bonus_map:
            c.create_text(cx, (y0 + y1) // 2, text=bonus_map[i],
                          font=("Helvetica", 7, "bold"), fill=_BONUS_GREEN, anchor="center")
    return c


def _order_tile_frame(
    parent,
    energy: int,
    points: int,
    dur: int,
    recovery: list,
    color: str,
    unit_w: int | None = None,
    tile_h: int | None = None,
    on_click=None,
) -> tk.Frame:
    """
    Build a segmented order tile frame.
    Each day segment shows ⚙×energy on the left; thin dark separators divide
    segments; the ♻ icon appears on whichever segment(s) are in the recovery
    offset list; +points sits on the right of the last segment.
    Pass unit_w/tile_h (pixels) to fix the physical size (order list).
    Leave them None to let the grid geometry manager size the widget (factory).
    """
    GEAR = "⚙"

    outer = tk.Frame(parent, bg=color)
    if unit_w is not None and tile_h is not None:
        outer.config(width=unit_w * dur, height=tile_h)
        outer.pack_propagate(False)

    def _bind_click(w):
        if on_click:
            w.bind("<Button-1>", lambda e: on_click())

    _bind_click(outer)

    for seg in range(dur):
        if seg > 0:
            sep = tk.Frame(outer, bg=THEME["bg_dark"], width=2)
            sep.pack(side="left", fill="y", pady=4)
            _bind_click(sep)

        seg_f = tk.Frame(outer, bg=color)
        seg_f.pack(side="left", fill="both", expand=True)
        _bind_click(seg_f)

        gl = tk.Label(
            seg_f, text=GEAR * energy, font=FONTS["tiny"],
            fg="white", bg=color, anchor="w", padx=4,
        )
        gl.pack(side="left", fill="y")
        _bind_click(gl)

        # ♻ icon on any segment whose offset is in the recovery list
        if seg in recovery:
            rl = tk.Label(
                seg_f, text=ICONS["recover"], font=FONTS["small"],
                fg="white", bg=color,
            )
            rl.pack(side="left")
            _bind_click(rl)

        if seg == dur - 1:          # +points always on the last segment
            pl = tk.Label(
                seg_f, text=f"+{points}", font=("Helvetica", 9, "bold"),
                fg="white", bg=color, anchor="e", padx=4,
            )
            pl.pack(side="right", fill="y")
            _bind_click(pl)

    return outer


# ─── Main Application ─────────────────────────────────────────────────────────

class DeepCarbPlannerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("DeepCarb Planner")
        self.configure(bg=THEME["bg_dark"])
        self.resizable(True, True)
        self.engine: GameEngine | None = None
        self._fw_running: bool = False
        self._fw_particles: list = []
        self._fw_after_id: str | None = None

        # ── Screen-size detection ─────────────────────────────────────────
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self._game_w = min(int(sw * 0.90), 1600)
        self._game_h = min(int(sh * 0.90), 1000)
        self._end_w  = min(int(sw * 0.70), 1100)
        self._end_h  = min(int(sh * 0.80),  900)
        self._tab_w  = min(int(sw * 0.90), 1600)
        self._tab_h  = min(int(sh * 0.90), 1000)

        self._build_start_screen()

    # =========================================================================
    # START SCREEN
    # =========================================================================

    def _build_start_screen(self):
        self._clear_window()
        frame = tk.Frame(self, bg=THEME["bg_dark"], padx=40, pady=40)
        frame.pack(expand=True)

        tk.Label(frame, text="DeepCarb Planner",
                 font=FONTS["title"], fg=THEME["accent"], bg=THEME["bg_dark"]
                 ).pack(pady=(0, 8))
        tk.Label(frame, text="HTWG Konstanz –  Energy Planning Game",
                 font=FONTS["small"], fg=THEME["muted"], bg=THEME["bg_dark"]
                 ).pack(pady=(0, 30))

        tk.Label(frame, text="Number of players:",
                 font=FONTS["normal"], fg="white", bg=THEME["bg_dark"]
                 ).pack()

        self.num_players_var = tk.IntVar(value=2)
        tk.Spinbox(
            frame, from_=2, to=4, textvariable=self.num_players_var,
            font=FONTS["normal"], width=4, justify="center",
        ).pack(pady=6)

        self.name_entries: list[tk.Entry] = []
        self.name_frame = tk.Frame(frame, bg=THEME["bg_dark"])
        self.name_frame.pack(pady=10)
        self.num_players_var.trace_add("write", lambda *_: self._update_name_entries())
        self._update_name_entries()

        _styled_button(frame, "Start Game", THEME["accent"],
                       self._start_game, padx=20, pady=8,
                       font=FONTS["heading"]).pack(pady=20)

        tk.Label(
            frame,
            text="5 working days  |  Collect energy  |  Fulfill orders  |  Maximize points",
            font=FONTS["small"], fg=THEME["white"], bg=THEME["bg_dark"],
        ).pack()

    def _update_name_entries(self):
        """
        Update the player name entry fields based on the selected number of players.
        """
        for w in self.name_frame.winfo_children():
            w.destroy()
        self.name_entries = []
        n = self.num_players_var.get()
        for i in range(n):
            row = tk.Frame(self.name_frame, bg=THEME["bg_dark"])
            row.pack(pady=3)
            tk.Label(
                row,
                text=f"Player {i+1} ({PLAYER_COLOR_NAMES[i]}):",
                font=FONTS["normal"], fg=PLAYER_COLORS[i], bg=THEME["bg_dark"],
                width=20, anchor="e",
            ).pack(side="left")
            entry = tk.Entry(row, font=FONTS["normal"], width=day_column_width)
            entry.insert(0, PLAYER_DEFAULT_NAMES[i])
            entry.pack(side="left", padx=6)
            self.name_entries.append(entry)

    def _start_game(self):
        names = [
            e.get().strip() or f"Player {i+1}"
            for i, e in enumerate(self.name_entries)
        ]
        self.engine = GameEngine(names)
        self._build_game_screen()

    # =========================================================================
    # MAIN GAME SCREEN
    # =========================================================================

    def _build_game_screen(self):
        self._clear_window()
        self.geometry(f"{self._game_w}x{self._game_h}")

        self._build_top_bar()
        self._build_main_area()
        self._build_action_bar()
        self._bind_game_keys()
        # Day 1 pre-day slot offers
        if self.engine.pre_day_pending:
            self._show_pre_day_popup()
        self._refresh_ui()

    # ── Layout builders ───────────────────────────────────────────────────────

    def _build_top_bar(self):
        top = tk.Frame(self, bg=THEME["bg_panel"], pady=6)
        top.pack(fill="x")

        self.day_label = tk.Label(
            top, text="", font=FONTS["day"],
            fg=THEME["accent"], bg=THEME["bg_panel"],
        )
        self.day_label.pack(side="left", padx=20)

        # Player name shown in their colour + separate action hint in white
        self.player_name_label = tk.Label(
            top, text="", font=FONTS["heading"],
            fg="white", bg=THEME["bg_panel"],
        )
        self.player_name_label.pack(side="left", padx=(10, 0))

        self.action_hint_label = tk.Label(
            top, text="", font=FONTS["heading"],
            fg="white", bg=THEME["bg_panel"],
        )
        self.action_hint_label.pack(side="left", padx=(4, 10))

        tk.Button(top, text="Rules", font=FONTS["small"],
                  bg=THEME["bg_taken"], fg="white", relief="flat", padx=10,
                  cursor="hand2", command=self._show_rules,
                  ).pack(side="right", padx=4)
        tk.Button(top, text="End Day", font=("Helvetica", 10, "bold"),
                  bg=THEME["warning"], fg="white", relief="flat", padx=10,
                  cursor="hand2", command=self._force_end_day,
                  ).pack(side="right", padx=10)
        tk.Button(top, text="↺ Restart", font=FONTS["small"],
                  bg=THEME["bg_taken"], fg=THEME["muted"], relief="flat", padx=10,
                  cursor="hand2", command=self._confirm_restart,
                  ).pack(side="right", padx=4)

    def _build_main_area(self):
        main = tk.Frame(self, bg=THEME["bg_dark"])
        main.pack(fill="both", expand=True)

        self._build_left_panel(main)
        self._build_right_panel(main)
        self._build_center_panel(main)  # center last so it fills remaining space

    def _build_left_panel(self, parent):
        left = tk.Frame(parent, bg=THEME["bg_dark"], width=400)
        left.pack(side="left", fill="y", padx=10, pady=10)
        left.pack_propagate(False)

        # Scrollable canvas that holds both Weather and Production Orders
        canvas = tk.Canvas(left, bg=THEME["bg_dark"], highlightthickness=0)
        vsb = ttk.Scrollbar(left, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        left_inner = tk.Frame(canvas, bg=THEME["bg_dark"])
        canvas.create_window((0, 0), window=left_inner, anchor="nw")
        left_inner.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        # Mousewheel scrolling
        canvas.bind(
            "<MouseWheel>",
            lambda e: canvas.yview_scroll(-1 * (e.delta // 120), "units"),
        )

        tk.Label(left_inner, text="Weather", font=FONTS["heading"],
                 fg=THEME["white"],
                 bg=THEME["bg_dark"]).pack(pady=(4, 0))
        self.weather_frame = tk.Frame(left_inner, bg=THEME["bg_dark"])
        self.weather_frame.pack(fill="x", pady=4)

        tk.Label(left_inner, text="Production Orders", font=FONTS["heading"],
                 fg=THEME["white"], bg=THEME["bg_dark"]).pack(pady=(12, 0))
        self.orders_frame = tk.Frame(left_inner, bg=THEME["bg_dark"])
        self.orders_frame.pack(fill="x", pady=4)

    def _build_center_panel(self, parent):
        center = tk.Frame(parent, bg=THEME["bg_dark"])
        center.pack(side="left", fill="both", expand=True, padx=6, pady=10)

        tk.Label(center, text="Factory Planners", font=FONTS["heading"],
                 fg=THEME["white"], bg=THEME["bg_dark"]).pack()

        canvas = tk.Canvas(center, bg=THEME["bg_dark"], highlightthickness=0)
        vsb = ttk.Scrollbar(center, orient="vertical",   command=canvas.yview)
        hsb = ttk.Scrollbar(center, orient="horizontal", command=canvas.xview)
        canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side="right",  fill="y")
        hsb.pack(side="bottom", fill="x")
        canvas.pack(side="left", fill="both", expand=True)

        self.factory_inner = tk.Frame(canvas, bg=THEME["bg_dark"])
        canvas.create_window((0, 0), window=self.factory_inner, anchor="nw")
        self.factory_inner.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        # Shift+MouseWheel scrolls horizontally
        canvas.bind(
            "<Shift-MouseWheel>",
            lambda e: canvas.xview_scroll(-1 * (e.delta // 120), "units"),
        )

    def _build_right_panel(self, parent):
        right = tk.Frame(parent, bg=THEME["bg_dark"], width=220)
        right.pack(side="right", fill="y", padx=10, pady=10)
        right.pack_propagate(False)

        tk.Label(right, text="Game Log", font=FONTS["heading"],
                 fg=THEME["muted"], bg=THEME["bg_dark"]).pack()

        log_frame = tk.Frame(right, bg=THEME["bg_dark"])
        log_frame.pack(fill="both", expand=True, pady=4)

        vsb = ttk.Scrollbar(log_frame, orient="vertical")
        vsb.pack(side="right", fill="y")

        self.log_text = tk.Text(
            log_frame, font=FONTS["log"], bg=THEME["bg_code"],
            fg="#ccc", wrap="word", state="disabled",
            relief="flat", yscrollcommand=vsb.set, height=12,
        )
        self.log_text.pack(side="left", fill="both", expand=True)
        vsb.config(command=self.log_text.yview)

        # Space below the log — energy pool histograms
        self.right_bottom = tk.Frame(right, bg=THEME["bg_dark"])
        self.right_bottom.pack(fill="both", expand=True, pady=(8, 0))

        tk.Label(self.right_bottom, text="Energy Pool", font=FONTS["heading"],
                 fg=THEME["muted"], bg=THEME["bg_dark"]).pack()

        self._hist_canvases: dict[str, tk.Canvas] = {}
        hist_colors = {"sun": THEME["sun"], "wind": THEME["wind"], "water": THEME["water"]}
        for etype in ("sun", "wind", "water"):
            row_f = tk.Frame(self.right_bottom, bg=THEME["bg_dark"])
            row_f.pack(fill="x", pady=2)
            icon = ICONS[etype]
            tk.Label(row_f, text=icon, font=FONTS["small"],
                     fg=hist_colors[etype], bg=THEME["bg_dark"], width=2).pack(side="left")
            c = tk.Canvas(row_f, bg=THEME["bg_panel"], height=110,
                          highlightthickness=0)
            c.pack(side="left", fill="x", expand=True)
            self._hist_canvases[etype] = c

    def _build_action_bar(self):
        self.action_frame = tk.Frame(self, bg=THEME["bg_panel"], pady=8)
        self.action_frame.pack(fill="x", padx=10, pady=(0, 6))

    # =========================================================================
    # UI REFRESH
    # =========================================================================

    def _refresh_ui(self):
        if self.engine.game_over:
            self._show_end_screen()
            return
        eng = self.engine
        player = eng.current_player()

        self.day_label.config(text=f"Day: {DAYS[eng.current_day]}")
        action_hint = (
            "Reveal a tile"
            if eng.action_state == "reveal"
            else "Buy energy  /  Take order  /  Pass"
        )
        self.player_name_label.config(text=f"{player.name}  ", fg=player.color)
        self.action_hint_label.config(text=f"|  {action_hint}", fg="white")

        self._draw_weather_tableau()
        self._draw_orders()
        self._draw_factory_planners()
        self._draw_action_bar()
        self._update_log()
        self._draw_histograms()

    # ── Panel drawers ─────────────────────────────────────────────────────────

    def _draw_weather_tableau(self):
        """Show all 5 days as columns; current day highlighted; only current-day tiles clickable."""
        for w in self.weather_frame.winfo_children():
            w.destroy()

        eng = self.engine
        type_color = {
            "sun":   THEME["sun"],
            "wind":  THEME["wind"],
            "water": THEME["water"],
        }

        for d, day in enumerate(DAYS):
            is_current = (d == eng.current_day)
            is_past    = (d < eng.current_day)
            col_bg = THEME["bg_today"] if is_current else THEME["bg_dark"]

            col = tk.Frame(
                self.weather_frame, bg=col_bg,
                highlightbackground=THEME["accent"] if is_current else THEME["dim"],
                highlightthickness=2,
            )
            col.pack(side="left", fill="y", padx=2, pady=2)

            # Day label
            tk.Label(
                col, text=day, font=FONTS["heading"],
                fg=THEME["accent"] if is_current else THEME["muted"],
                bg=col_bg, padx=8, pady=4,
            ).pack(fill="x")

            wc = eng.weather_cards[d]
            for tile in wc.tiles:
                on   = tile["on_card"]
                icon = ICONS.get(tile["type"], "?")

                if not on:
                    continue   # taken tiles simply vanish from the column
                elif tile["revealed"]:
                    bg   = type_color.get(tile["type"], "#888")
                    text = icon * tile["value"] if tile["value"] > 0 else f"{icon}—"
                    fg   = THEME["bg_dark"]
                else:
                    # Hidden: use the type color but darkened
                    base = type_color.get(tile["type"], "#888")
                    bg   = _dim_color(base, 0.35)
                    text = f"{icon}?"
                    fg   = "#ffffff"

                clickable = is_current and on
                tk.Button(
                    col, text=text, font=FONTS["small"],
                    bg=bg, fg=fg, relief="flat", padx=6, pady=4,
                    state="normal" if clickable else "disabled",
                    cursor="hand2" if clickable else "arrow",
                    command=lambda t=tile: self._on_weather_tile_click(t),
                ).pack(fill="x", padx=4, pady=1)

    def _draw_orders(self):
        for w in self.orders_frame.winfo_children():
            w.destroy()

        TILE_UNIT = 85
        TILE_H    = 30

        for order in self.engine.order_display:
            dur    = order["duration"]
            color  = _dur_color(dur)
            tile = _order_tile_frame(
                self.orders_frame,
                energy=order["energy"],
                points=order["points"],
                dur=dur,
                recovery=order.get("recovery", []),
                color=color,
                unit_w=TILE_UNIT,
                tile_h=TILE_H,
                on_click=lambda o=order: self._on_order_click(o),
            )
            tile.config(cursor="hand2")
            tile.pack(anchor="w", pady=2)

        if not self.engine.order_display:
            _label(self.orders_frame, "No orders available", "small").pack()

    def _draw_factory_planners(self):
        for w in self.factory_inner.winfo_children():
            w.destroy()
        eng = self.engine

        # ── Column headers ────────────────────────────────────────────────────
        header = tk.Frame(self.factory_inner, bg=THEME["bg_dark"])
        header.pack(fill="x", pady=(4, 0))

        tk.Label(header, text="Player", font=FONTS["heading"],
                 fg=THEME["muted"], bg=THEME["bg_dark"], width=12
                 ).grid(row=0, column=0)

        for d, day in enumerate(DAYS):
            color = THEME["accent"] if d == eng.current_day else THEME["dim"]
            tk.Label(header, text=day, font=FONTS["heading"],
                     fg=color, bg=THEME["bg_dark"], width=day_column_width
                     ).grid(row=0, column=d + 1)

        tk.Label(header, text=ICONS["battery"], font=FONTS["small"],
                 fg=THEME["battery"], bg=THEME["bg_dark"], width=4
                 ).grid(row=0, column=6)
        tk.Label(header, text=f"+{ICONS['battery']}", font=FONTS["small"],
                 fg=THEME["battery"], bg=THEME["bg_dark"], width=4
                 ).grid(row=0, column=7)
        tk.Label(header, text="CO\u2082", font=FONTS["small"],
                 fg=THEME["co2"], bg=THEME["bg_dark"], width=4
                 ).grid(row=0, column=8)

        # ── Per-player rows ────────────────────────────────────────────────────
        energy_colors = {
            "sun":   THEME["sun"],
            "wind":  THEME["wind"],
            "water": THEME["water"],
        }

        for player in eng.players:
            is_active = (not eng.game_over) and (player is eng.current_player())
            pframe = tk.Frame(
                self.factory_inner, bg=THEME["bg_dark"],
                highlightbackground=player.color,
                highlightthickness=8 if is_active else 2,
            )
            pframe.pack(fill="x", padx=4, pady=3)

            name_fg = player.color if is_active else THEME["muted"]
            name_font = FONTS["heading"] if not is_active else ("Helvetica", 12, "bold")
            tk.Label(
                pframe, text=player.name, font=name_font,
                fg=name_fg, bg=THEME["bg_dark"], width=12,
            ).grid(row=0, column=0, rowspan=ROWS_PER_DAY, sticky="nsew")

            # Cells consumed (col>0) by a spanning order tile
            consumed: set[tuple[int, int]] = set()
            for d in range(len(DAYS)):
                for r in range(ROWS_PER_DAY):
                    t = player.factory_planner[d][r]
                    if t and t["type"] == "order" and t["day_offset"] == 0:
                        for off in range(1, t["total_days"]):
                            consumed.add((d + off, r))

            for d in range(len(DAYS)):
                for r in range(ROWS_PER_DAY):
                    if (d, r) in consumed:
                        continue   # covered by a spanning tile placed earlier

                    tile = player.factory_planner[d][r]

                    if tile and tile["type"] == "order" and tile["day_offset"] == 0:
                        dur = tile["total_days"]
                        f = _order_tile_frame(
                            pframe,
                            energy=tile["energy"],
                            points=tile["points"],
                            dur=dur,
                            recovery=tile.get("recovery_offsets", []),
                            color=_dur_color(dur),
                        )
                        f.grid(
                            row=r, column=d + 1, columnspan=dur,
                            padx=1, pady=1, sticky="nsew",
                        )
                    else:
                        bg, text = self._cell_appearance(
                            tile, d, eng.current_day, energy_colors
                        )
                        fg = THEME["bg_dark"] if (tile and tile["type"] == "energy") else "white"
                        tk.Label(
                            pframe, text=text, font=FONTS["small"],
                            bg=bg, fg=fg,
                            width=day_column_width +4, height=2, relief="solid", bd=0, padx=2,
                        ).grid(row=r, column=d + 1, padx=1, pady=1, sticky="nsew")

            # Battery columns + CO₂
            bat_h        = ROWS_PER_DAY * 28
            base_stored  = min(player.battery_storage, BATTERY_CAPACITY)
            # bonus_map: segment index (0=bottom) → label for thresholds inside base battery
            base_bonus_map = {
                v - 1: f"+{pts}"
                for v, pts in BATTERY_BONUS.items()
                if 1 <= v <= BATTERY_CAPACITY
            }
            _battery_canvas(
                pframe, stored=base_stored, capacity=BATTERY_CAPACITY,
                w=28, h=bat_h, bonus_map=base_bonus_map,
            ).grid(row=0, column=6, rowspan=ROWS_PER_DAY, padx=2, pady=2)

            extra_cap    = player.extra_battery_slots
            extra_stored = max(0, player.battery_storage - BATTERY_CAPACITY)
            if extra_cap > 0:
                extra_h = bat_h * extra_cap // BATTERY_CAPACITY
                extra_bonus_map = {
                    v - BATTERY_CAPACITY - 1: f"+{pts}"
                    for v, pts in BATTERY_BONUS.items()
                    if BATTERY_CAPACITY < v <= BATTERY_CAPACITY + extra_cap
                }
                _battery_canvas(
                    pframe, stored=extra_stored, capacity=extra_cap,
                    w=28, h=extra_h, bonus_map=extra_bonus_map,
                ).grid(row=0, column=7, rowspan=ROWS_PER_DAY, padx=2, pady=2)
            else:
                tk.Label(pframe, bg=THEME["bg_dark"], width=4
                         ).grid(row=0, column=7, rowspan=ROWS_PER_DAY)

            tk.Label(
                pframe,
                text=str(player.conventional_energy),
                font=FONTS["heading"], fg=THEME["co2"], bg=THEME["bg_dark"], width=4,
            ).grid(row=0, column=8, rowspan=ROWS_PER_DAY)

    @staticmethod
    def _cell_appearance(tile, day: int, current_day: int, energy_colors: dict) -> tuple[str, str]:
        """Return (background_colour, label_text) for a single factory cell."""
        if tile is None:
            bg = THEME["bg_today"] if day == current_day else THEME["bg_cell"]
            return bg, ""

        if tile["type"] == "energy":
            bg   = energy_colors.get(tile["energy_type"], THEME["muted"])
            icon = ICONS.get(tile["energy_type"], "")
            return bg, icon * tile["value"] if tile["value"] > 0 else icon

        if tile["type"] == "order":
            rec  = ICONS["recover"] if tile.get("recovery") else ""
            off  = tile.get("day_offset", 0)
            last = tile.get("total_days", 1) - 1
            if off == 0:
                text = f"{ICONS['order']}{tile['energy']}{ICONS['energy']}{rec}"
            elif off == last:
                text = f"{tile['points']}{ICONS['done']}{rec}"
            else:
                text = f"{ICONS['cont']}{tile['energy']}{ICONS['energy']}{rec}"
            return THEME["order"], text

        return THEME["bg_taken"], ""

    def _draw_action_bar(self):
        for w in self.action_frame.winfo_children():
            w.destroy()
        eng = self.engine
        player = eng.current_player()

        # Top row: player name + pass button + stats
        top_row = tk.Frame(self.action_frame, bg=THEME["bg_panel"])
        top_row.pack(fill="x")

        tk.Label(
            top_row,
            text=f"{player.name}'s turn  —  ",
            font=FONTS["normal"], fg=player.color, bg=THEME["bg_panel"],
        ).pack(side="left", padx=8)

        if eng.action_state == "action":
            tk.Button(
                top_row, text="Pass (skip action)  [Space]",
                font=FONTS["small"], bg=THEME["bg_taken"], fg="white",
                relief="flat", padx=10, pady=4, cursor="hand2",
                command=self._on_pass,
            ).pack(side="left", padx=6)

        summary = (
            f"Battery: {player.battery_storage}/{player.battery_capacity}  |  "
            f"CO₂: {player.conventional_energy}  |  "
            f"Energy today: {player.energy_in_day(eng.current_day)} {ICONS['energy']}  |  "
            f"Need today: {player.energy_needed_day(eng.current_day)} {ICONS['energy']}"
        )
        tk.Label(
            top_row, text=summary,
            font=FONTS["small"], fg=THEME["muted"], bg=THEME["bg_panel"],
        ).pack(side="left", padx=day_column_width)

        # Bottom row: keyboard legend
        hint = tk.Label(
            self.action_frame,
            text="Keys:  1–9 → weather tile  ·  Q–O → order 1–9  ·  Space/P → pass  ·  D → end day",
            font=FONTS["tiny"], fg=THEME["muted"], bg=THEME["bg_panel"],
        )
        hint.pack(anchor="w", padx=8)

    def _update_log(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        for msg in self.engine.log_messages[-60:]:
            self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    # =========================================================================
    # KEYBOARD SHORTCUTS
    # =========================================================================

    # Order keys: Q W E R T Y U I O  → orders 1–9
    _ORDER_KEYS = "qwertyuio"

    def _bind_game_keys(self):
        self.bind("<Key>", self._on_key)

    def _on_key(self, event):
        if self.engine is None or self.engine.game_over:
            return
        # Don’t fire if a modal dialog (Toplevel with grab) is active
        try:
            grab = self.grab_current()
            if grab is not None and grab is not self:
                return
        except Exception:
            return

        k = event.keysym.lower()

        # 1–9 → interact with the Nth on-card tile of today’s weather card 
        if k in "123456789":
            idx = int(k) - 1
            tiles = [t for t in self.engine.weather_card().tiles if t["on_card"]]
            if idx < len(tiles):
                self._on_weather_tile_click(tiles[idx])
            return

        # Q–O → select order by index
        if k in self._ORDER_KEYS:
            idx = self._ORDER_KEYS.index(k)
            orders = self.engine.order_display
            if idx < len(orders):
                self._on_order_click(orders[idx])
            return

        # Space or P → pass
        if k in ("space", "p"):
            if self.engine.action_state == "action":
                self._on_pass()
            return

        # D → force end day
        if k == "d":
            self._force_end_day()
            return

    # =========================================================================
    # USER INTERACTIONS
    # =========================================================================

    def _on_weather_tile_click(self, tile: dict):
        eng = self.engine
        if not tile["on_card"]:
            return

        if eng.action_state == "reveal":
            eng.do_reveal_tile(tile)
            self._refresh_ui()
            return

        if eng.action_state == "action":
            player = eng.current_player()
            if player.free_slots_day(eng.current_day) == 0:
                messagebox.showwarning("No space", "Your factory is full for today!")
                return
            eng.do_buy_energy(tile)
            # Refresh and force-render so the tile appears in the factory
            # planner (and vanishes from the weather column) before any
            # end-of-day popup blocks the event loop.
            self._refresh_ui()
            self.update()
            self._post_action()

    def _on_order_click(self, order: dict):
        eng = self.engine
        if eng.action_state == "reveal":
            messagebox.showinfo(
                "Reveal first",
                "You must reveal a weather tile before taking an order.",
            )
            return

        player = eng.current_player()
        allowed = eng.allowed_start_days(player, order)
        if not allowed:
            messagebox.showwarning("No space", "No room in your factory for this order!")
            return

        start = allowed[0] if len(allowed) == 1 else self._ask_start_day(allowed, order)
        if start is None:
            return

        eng.do_take_order(order, start)
        self._post_action()

    def _on_pass(self):
        self.engine.do_pass()
        self._refresh_ui()

    def _force_end_day(self):
        if messagebox.askyesno(
            "End Day",
            f"Force end of {DAYS[self.engine.current_day]}?",
        ):
            self.engine.force_end_of_day()
            self._post_action()

    def _post_action(self):
        if self.engine.day_summary is not None:
            summary = self.engine.day_summary
            self.engine.day_summary = None
            self._show_day_summary(summary)   # blocks until player closes it
        if self.engine.game_over:
            self._show_end_screen()
        else:
            if self.engine.pre_day_pending:
                self._show_pre_day_popup()    # blocks until player closes it
            self._refresh_ui()

    # ── Pre-day slot purchase popup ─────────────────────────────────────────

    def _show_pre_day_popup(self):
        """Shown at the start of every day so players can buy a battery slot bundle."""
        self.engine.pre_day_pending = False
        day_name = DAYS[self.engine.current_day]
        players  = self.engine.players

        win = tk.Toplevel(self)
        win.title(f"Start of {day_name} — Battery Upgrades")
        win.configure(bg=THEME["bg_dark"])
        win.grab_set()
        win.resizable(False, False)

        tk.Label(
            win, text=f"Start of {day_name}",
            font=FONTS["title"], fg=THEME["accent"], bg=THEME["bg_dark"],
        ).pack(pady=(20, 4), padx=30)
        tk.Label(
            win,
            text=(
                f"{ICONS['battery']} Buy +{EXTRA_BATTERY_SLOTS_PER_PURCHASE} battery slots "
                f"for −{EXTRA_BATTERY_COST} pt"
            ),
            font=FONTS["heading"], fg=THEME["battery"], bg=THEME["bg_dark"],
        ).pack(pady=(0, 4))
        tk.Label(
            win,
            text=f"Keys 1–{len(players)} to toggle  ·  Enter to confirm  ·  max {MAX_EXTRA_BATTERY_SLOTS} extra slots",
            font=FONTS["tiny"], fg=THEME["muted"], bg=THEME["bg_dark"],
        ).pack(pady=(0, 14))

        slot_purchased: dict = {}   # player → bool
        slot_btn_widgets: dict = {}

        def _update_btn(player):
            bought   = slot_purchased.get(player, False)
            btn      = slot_btn_widgets[player]
            can_buy  = player.extra_battery_slots + EXTRA_BATTERY_SLOTS_PER_PURCHASE <= MAX_EXTRA_BATTERY_SLOTS
            cap_now  = player.battery_capacity
            cap_next = cap_now + EXTRA_BATTERY_SLOTS_PER_PURCHASE
            if bought:
                btn.config(
                    text=f"✓ +{EXTRA_BATTERY_SLOTS_PER_PURCHASE} slots bought  (cap {cap_now+EXTRA_BATTERY_SLOTS_PER_PURCHASE})  [toggle to undo]",
                    bg=THEME["accent"], fg=THEME["bg_dark"],
                )
            elif not can_buy:
                btn.config(
                    text=f"At max capacity ({cap_now} slots)",
                    bg=THEME["bg_taken"], fg=THEME["dim"],
                    state="disabled",
                )
            else:
                btn.config(
                    text=f"{ICONS['battery']} Buy +{EXTRA_BATTERY_SLOTS_PER_PURCHASE} slots  "
                         f"({cap_now} → {cap_next} cap)  −{EXTRA_BATTERY_COST} pt",
                    bg=THEME["bg_taken"], fg=THEME["muted"],
                    state="normal",
                )

        def _toggle(player):
            bought  = slot_purchased.get(player, False)
            can_buy = player.extra_battery_slots + EXTRA_BATTERY_SLOTS_PER_PURCHASE <= MAX_EXTRA_BATTERY_SLOTS
            if not bought and not can_buy:
                return
            slot_purchased[player] = not bought
            _update_btn(player)

        content = tk.Frame(win, bg=THEME["bg_dark"])
        content.pack(padx=30, fill="x")

        for i, p in enumerate(players):
            row_f = tk.Frame(content, bg=THEME["bg_panel"], pady=6, padx=12)
            row_f.pack(fill="x", pady=3)
            tk.Label(
                row_f, text=f"{i+1}.  {p.name}",
                font=FONTS["normal"], fg=p.color, bg=THEME["bg_panel"],
                width=14, anchor="w",
            ).pack(side="left")
            btn = tk.Button(
                row_f, text="", font=FONTS["small"],
                bg=THEME["bg_taken"], fg=THEME["muted"],
                relief="flat", padx=8, pady=3, cursor="hand2",
                command=lambda pl=p: _toggle(pl),
            )
            btn.pack(side="left", padx=8)
            slot_btn_widgets[p] = btn
            slot_purchased[p] = False
            _update_btn(p)

        def _confirm():
            for p in players:
                if slot_purchased.get(p, False):
                    self.engine.do_buy_slot_bundle(p)
            win.destroy()

        _styled_button(
            win, f"Begin {day_name}  [Enter]", THEME["accent"], _confirm,
            padx=20, pady=8, font=FONTS["heading"],
        ).pack(pady=16)

        def _popup_key(event):
            k = event.keysym
            if k in ("Return", "KP_Enter"):
                _confirm()
            elif k.isdigit():
                idx = int(k) - 1
                if 0 <= idx < len(players):
                    _toggle(players[idx])

        win.bind("<Key>", _popup_key)
        win.focus_set()
        self.wait_window(win)

    # ── Day summary popup ────────────────────────────────────────────────────

    def _show_day_summary(self, summary: dict):
        """Modal window shown after every working day with each player's balance."""
        win = tk.Toplevel(self)
        win.title(f"End of {summary['day_name']} — Day Summary")
        win.configure(bg=THEME["bg_dark"])
        win.grab_set()
        win.resizable(True, True)
        win.geometry("520x560")

        # ── Fixed header ──────────────────────────────────────────────────────
        header_frame = tk.Frame(win, bg=THEME["bg_dark"])
        header_frame.pack(fill="x")
        tk.Label(
            header_frame, text=f"End of {summary['day_name']}",
            font=FONTS["title"], fg=THEME["accent"], bg=THEME["bg_dark"],
        ).pack(pady=(20, 4), padx=30)
        tk.Label(
            header_frame, text="Energy balance for each player",
            font=FONTS["small"], fg=THEME["muted"], bg=THEME["bg_dark"],
        ).pack(pady=(0, 16))

        # ── Scrollable middle section ─────────────────────────────────────────
        scroll_canvas = tk.Canvas(win, bg=THEME["bg_dark"], highlightthickness=0)
        vsb = ttk.Scrollbar(win, orient="vertical", command=scroll_canvas.yview)
        scroll_canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        scroll_canvas.pack(side="top", fill="both", expand=True)
        scroll_canvas.bind(
            "<MouseWheel>",
            lambda e: scroll_canvas.yview_scroll(-1 * (e.delta // 120), "units"),
        )

        inner = tk.Frame(scroll_canvas, bg=THEME["bg_dark"])
        win_id = scroll_canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind(
            "<Configure>",
            lambda e: scroll_canvas.configure(scrollregion=scroll_canvas.bbox("all")),
        )
        scroll_canvas.bind(
            "<Configure>",
            lambda e: scroll_canvas.itemconfig(win_id, width=e.width),
        )

        for ps in summary["players"]:
            p = ps["player"]
            frame = tk.Frame(inner, bg=THEME["bg_panel"], padx=16, pady=10)
            frame.pack(fill="x", padx=20, pady=4)

            # Player name header
            tk.Label(
                frame, text=p.name, font=FONTS["heading"],
                fg=p.color, bg=THEME["bg_panel"], anchor="w",
            ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))

            rows = [
                (f"{ICONS['energy']} Energy collected",  f"+{ps['available']}",  THEME["accent"]),
                (f"{ICONS['energy']} Energy needed",     f"−{ps['needed']}",     THEME["muted"]),
                ("Balance",                              _signed(ps["balance"]),
                 THEME["accent"] if ps["balance"] >= 0 else THEME["warning"]),
            ]
            if ps["batteries_stored"]:
                rows.append((f"{ICONS['battery']} Batteries stored",
                             f"+{ps['batteries_stored']}", THEME["battery"]))
            if ps["batteries_used"]:
                rows.append((f"{ICONS['battery']} Batteries used",
                             f"−{ps['batteries_used']}", THEME["battery"]))
            if ps["conv_bought"]:
                rows.append(("⚠ Conventional energy bought",
                             f"+{ps['conv_bought']}  (−{ps['conv_bought'] * CONV_ENERGY_PENALTY} pts)",
                             THEME["warning"]))
            if ps["recovered"]:
                rows.append((f"{ICONS['recover']} Energy recovered",
                             f"+{ps['recovered']}", THEME["accent"]))
            rows.append((f"{ICONS['battery']} Battery storage now",
                         f"{ps['battery_total']}/{p.battery_capacity}", THEME["battery"]))

            for r, (label, value, color) in enumerate(rows, start=1):
                tk.Label(frame, text=label, font=FONTS["small"],
                         fg=THEME["muted"], bg=THEME["bg_panel"],
                         anchor="w", width=30).grid(row=r, column=0, sticky="w")
                tk.Label(frame, text=value, font=FONTS["small"],
                         fg=color, bg=THEME["bg_panel"],
                         anchor="e", width=18).grid(row=r, column=1, sticky="e")

        # ── Next-day turn order ──────────────────────────────────────────
        if "next_day_order" in summary:
            order_frame = tk.Frame(inner, bg=THEME["bg_panel"], padx=16, pady=10)
            order_frame.pack(fill="x", padx=20, pady=(0, 4))
            tk.Label(
                order_frame,
                text=f"Turn order for {summary['next_day']}:",
                font=FONTS["heading"], fg=THEME["accent"], bg=THEME["bg_panel"],
                anchor="w",
            ).pack(anchor="w", pady=(0, 6))
            for pos, p in enumerate(summary["next_day_order"], start=1):
                needed = p.energy_needed_day(self.engine.current_day)
                tk.Label(
                    order_frame,
                    text=f"{pos}.  {p.name}   (needs {needed} {ICONS['energy']})",
                    font=FONTS["normal"], fg=p.color, bg=THEME["bg_panel"],
                    anchor="w",
                ).pack(anchor="w")

        # ── Fixed footer: dismiss button ──────────────────────────────────────
        is_last = self.engine.game_over
        btn_text = "See Final Scores" if is_last else f"Start {DAYS[self.engine.current_day]}"
        _styled_button(
            win, btn_text, THEME["accent"], win.destroy,
            padx=20, pady=8, font=FONTS["heading"],
        ).pack(pady=12)

        win.bind("<Return>", lambda e: win.destroy())
        win.bind("<KP_Enter>", lambda e: win.destroy())
        win.focus_set()

        self.wait_window(win)

    def _draw_histograms(self):
        """Draw proportional-fill vertical bar charts for each energy type.
        All three charts share the same x-axis positions so identical values
        (e.g. all '2' bars) line up vertically across the three rows."""
        stats = self.engine.pool_stats()
        hist_colors = {"sun": THEME["sun"], "wind": THEME["wind"], "water": THEME["water"]}
        gray = "#555566"
        PAD_L, PAD_R, PAD_T, PAD_B = 4, 4, 4, 16  # px; bottom reserved for labels

        # Build a shared, sorted value axis from all energy types combined
        all_values = sorted({v for etype in ("sun", "wind", "water")
                               for v in stats.get(etype, {}).keys()})
        if not all_values:
            return
        n = len(all_values)
        val_index = {v: i for i, v in enumerate(all_values)}

        # Global max total so bar heights are comparable across types
        max_tot = max(
            (tot for etype in ("sun", "wind", "water")
             for tot, _ in stats.get(etype, {}).values()),
            default=1,
        ) or 1

        for etype, canvas in self._hist_canvases.items():
            canvas.delete("all")
            canvas.update_idletasks()
            W = canvas.winfo_width() or 180
            H = canvas.winfo_height() or 55

            type_stats = stats.get(etype, {})
            chart_h  = H - PAD_T - PAD_B
            color    = hist_colors[etype]
            slot_w   = (W - PAD_L - PAD_R) / n
            bar_w    = max(4, int(slot_w) - 2)
            y_bot    = H - PAD_B

            for v in all_values:
                i = val_index[v]
                x0 = int(PAD_L + i * slot_w)
                x1 = x0 + bar_w

                if v in type_stats:
                    total, used = type_stats[v]
                    full_h   = int(chart_h * total / max_tot)
                    used_h   = int(full_h * used / total) if total else 0
                    remain_h = full_h - used_h
                    if used_h > 0:
                        canvas.create_rectangle(x0, y_bot - used_h, x1, y_bot,
                                                fill=gray, outline="")
                    if remain_h > 0:
                        canvas.create_rectangle(x0, y_bot - full_h, x1, y_bot - used_h,
                                                fill=color, outline="")

                # value label — drawn even if this type has no bar for that value
                canvas.create_text((x0 + x1) // 2, H - PAD_B + 4,
                                   text=str(v), font=("Helvetica", 7),
                                   fill=THEME["muted"], anchor="n")

    # ── Day-selection dialog ──────────────────────────────────────────────────

    def _ask_start_day(self, allowed: list[int], order: dict) -> int | None:
        """Pop a small dialog to let the player choose which day to start an order."""
        win = tk.Toplevel(self)
        win.title("Choose start day")
        win.configure(bg=THEME["bg_dark"])
        win.grab_set()
        win.resizable(False, False)

        dur = order["duration"]
        tk.Label(
            win,
            text=f"Start this {dur}-day order on:",
            font=FONTS["normal"], fg="white", bg=THEME["bg_dark"],
        ).pack(pady=(14, 4), padx=24)
        tk.Label(
            win,
            text="↑ ↓ to move  ·  Enter to confirm  ·  Esc to cancel",
            font=FONTS["tiny"], fg=THEME["dim"], bg=THEME["bg_dark"],
        ).pack(pady=(0, 10))

        # Track selection by list index so arrow keys stay within bounds
        sel_idx = tk.IntVar(value=0)
        btn_widgets: list[tk.Button] = []

        def _highlight(idx: int):
            for i, b in enumerate(btn_widgets):
                if i == idx:
                    b.config(bg=THEME["accent"], fg=THEME["bg_dark"],
                             relief="solid", bd=2)
                else:
                    b.config(bg=THEME["bg_cell"], fg=THEME["accent"],
                             relief="flat", bd=0)

        for i, d in enumerate(allowed):
            b = tk.Button(
                win, text=DAYS[d], font=FONTS["heading"],
                bg=THEME["bg_cell"], fg=THEME["accent"],
                relief="flat", padx=24, pady=6, cursor="hand2",
                command=lambda idx=i: (sel_idx.set(idx), _highlight(idx)),
            )
            b.pack(fill="x", padx=24, pady=3)
            btn_widgets.append(b)

        _highlight(0)

        result: list[int | None] = [None]

        def confirm():
            result[0] = allowed[sel_idx.get()]
            win.destroy()

        def on_key(event):
            k = event.keysym
            if k == "Up":
                new = (sel_idx.get() - 1) % len(allowed)
                sel_idx.set(new); _highlight(new)
            elif k == "Down":
                new = (sel_idx.get() + 1) % len(allowed)
                sel_idx.set(new); _highlight(new)
            elif k in ("Return", "KP_Enter"):
                confirm()
            elif k == "Escape":
                win.destroy()

        win.bind("<Key>", on_key)
        win.focus_set()

        _styled_button(win, "Place Order  [Enter]", THEME["accent"], confirm,
                       padx=12, font=FONTS["heading"]).pack(pady=12)
        self.wait_window(win)
        return result[0]

    # =========================================================================
    # END SCREEN
    # =========================================================================

    def _show_end_screen(self):
        self._stop_fireworks()
        self._clear_window()
        self.geometry(f"{self._end_w}x{self._end_h}")

        # ── Fireworks strip ────────────────────────────────────────────────────
        fw_canvas = tk.Canvas(self, bg=THEME["bg_dark"], height=110,
                               highlightthickness=0)
        fw_canvas.pack(fill="x")

        # ── Scores frame ──────────────────────────────────────────────────────
        frame = tk.Frame(self, bg=THEME["bg_dark"], padx=40, pady=20)
        frame.pack(expand=True, fill="both")

        ranked = sorted(self.engine.players, key=lambda p: -p.compute_score())
        winner = ranked[0]

        tk.Label(
            frame,
            text=f"🏆  {winner.name} wins!",
            font=FONTS["title"], fg=winner.color, bg=THEME["bg_dark"],
        ).pack(pady=(0, 16))

        medals = ["🥇", "🥈", "🥉", "  "]
        for rank, p in enumerate(ranked):
            score = p.compute_score()
            row = tk.Frame(frame, bg=THEME["bg_panel"], pady=8, padx=20)
            row.pack(fill="x", pady=4)

            medal = medals[min(rank, 3)]
            tk.Label(row, text=f"{medal}  {p.name}", font=FONTS["heading"],
                     fg=p.color, bg=THEME["bg_panel"], width=18, anchor="w",
                     ).pack(side="left")
            tk.Label(row, text=f"{score} pts", font=FONTS["heading"],
                     fg="white", bg=THEME["bg_panel"]).pack(side="right")
            detail = (
                f"CO₂: −{p.conventional_energy * CONV_ENERGY_PENALTY}  "
                f"Battery: {p.battery_storage} {ICONS['battery']}"
            )
            tk.Label(row, text=detail, font=FONTS["small"],
                     fg=THEME["muted"], bg=THEME["bg_panel"]).pack(side="right", padx=20)

        btn_row = tk.Frame(frame, bg=THEME["bg_dark"])
        btn_row.pack(pady=24)
        _styled_button(btn_row, "View Tableau", THEME["muted"],
                       self._show_end_tableau,
                       padx=16, pady=8, font=FONTS["normal"]).pack(side="left", padx=8)
        _styled_button(btn_row, "Play Again", THEME["accent"],
                       self._build_start_screen,
                       padx=20, pady=8, font=FONTS["heading"]).pack(side="left", padx=8)

        self._start_fireworks(fw_canvas)

    # =========================================================================
    # END TABLEAU (read-only game view after game over)
    # =========================================================================

    def _show_end_tableau(self):
        """Show the full game tableau in read-only mode; a Back button returns to scores."""
        self._stop_fireworks()
        self._clear_window()
        self.geometry(f"{self._tab_w}x{self._tab_h}")

        self._build_top_bar()
        self._build_main_area()

        # ── Score summary strip ───────────────────────────────────────────────
        summary_outer = tk.Frame(self, bg=THEME["bg_panel"], pady=6)
        summary_outer.pack(fill="x", padx=0)

        ranked = sorted(self.engine.players, key=lambda p: -p.compute_score())
        for p in ranked:
            bd = p.score_breakdown()
            total = p.compute_score()
            card = tk.Frame(summary_outer, bg=THEME["bg_panel"],
                            highlightbackground=p.color, highlightthickness=2)
            card.pack(side="left", padx=8, pady=4, fill="y")

            tk.Label(card, text=p.name, font=FONTS["heading"],
                     fg=p.color, bg=THEME["bg_panel"], anchor="w", padx=8
                     ).grid(row=0, column=0, columnspan=2, sticky="w")

            rows = [
                (f"Orders {ICONS['order']}",         f"+{bd['order_pts']} pts",   THEME["order"]),
                (f"Battery bonus {ICONS['battery']}", f"+{bd['battery_bonus']} pts", THEME["battery"]),
                (f"CO\u2082 penalty {ICONS['co2']}",    f"{bd['co2_penalty']} pts",  THEME["warning"]),
            ]
            if bd["slot_cost"] < 0:
                rows.append((f"{ICONS['battery']} Slot purchases",
                             f"{bd['slot_cost']} pts", THEME["warning"]))
            rows += [
                (f"Energy collected {ICONS['energy']}", f"{bd['total_energy']}",   THEME["muted"]),
                ("Total",                             f"{total} pts",             "white"),
            ]
            for r, (lbl, val, col) in enumerate(rows, start=1):
                tk.Label(card, text=lbl, font=FONTS["small"],
                         fg=THEME["muted"], bg=THEME["bg_panel"],
                         anchor="w", padx=8, width=18).grid(row=r, column=0, sticky="w")
                tk.Label(card, text=val, font=FONTS["small"],
                         fg=col, bg=THEME["bg_panel"],
                         anchor="e", padx=8, width=10).grid(row=r, column=1, sticky="e")

        # ── Action bar with Back button ───────────────────────────────────────
        self.action_frame = tk.Frame(self, bg=THEME["bg_panel"], pady=8)
        self.action_frame.pack(fill="x", padx=10, pady=(0, 6))
        _styled_button(
            self.action_frame, "← Back to Results", THEME["accent"],
            self._show_end_screen,
            padx=16, pady=4, font=FONTS["heading"],
        ).pack(side="left", padx=8)

        # Fill in top-bar labels for final state
        self.day_label.config(text="Final Tableau")
        self.player_name_label.config(text="Game Over", fg=THEME["accent"])
        self.action_hint_label.config(text="")

        self._draw_weather_tableau()
        self._draw_orders()
        self._draw_factory_planners()
        self._update_log()
        self._draw_histograms()

    # =========================================================================
    # FIREWORKS ANIMATION
    # =========================================================================

    def _start_fireworks(self, canvas: tk.Canvas):
        import random, math
        self._fw_running = True
        self._fw_particles = []

        burst_colors = [
            THEME["accent"], THEME["sun"], THEME["warning"],
            "#ff69b4", "#9b59b6", "#3498db", "#e74c3c", "#2ecc71",
        ]

        def launch():
            if not self._fw_running:
                return
            try:
                canvas.update_idletasks()
                W = canvas.winfo_width() or 600
                H = canvas.winfo_height() or 110
            except tk.TclError:
                return
            x = random.randint(W // 6, 5 * W // 6)
            y = random.randint(12, max(13, H - 20))
            color = random.choice(burst_colors)
            for _ in range(20):
                angle = random.uniform(0, 2 * math.pi)
                speed = random.uniform(2, 8)
                vx = math.cos(angle) * speed
                vy = math.sin(angle) * speed - 1.5
                size = random.randint(3, 6)
                life = random.randint(18, 32)
                try:
                    oid = canvas.create_oval(
                        x - size, y - size, x + size, y + size,
                        fill=color, outline="",
                    )
                except tk.TclError:
                    return
                self._fw_particles.append({
                    "id": oid, "x": float(x), "y": float(y),
                    "vx": vx, "vy": vy, "life": life, "max_life": life, "size": size,
                })

        def tick():
            if not self._fw_running:
                return
            try:
                dead = []
                for p in self._fw_particles:
                    p["x"] += p["vx"]
                    p["y"] += p["vy"]
                    p["vy"] += 0.22   # gravity
                    p["life"] -= 1
                    s = max(1, int(p["size"] * p["life"] / p["max_life"]))
                    canvas.coords(
                        p["id"],
                        p["x"] - s, p["y"] - s,
                        p["x"] + s, p["y"] + s,
                    )
                    if p["life"] <= 0:
                        canvas.delete(p["id"])
                        dead.append(p)
                for p in dead:
                    self._fw_particles.remove(p)

                if random.random() < 0.10:   # ~10% per frame to launch a new burst
                    launch()

                self._fw_after_id = self.after(40, tick)
            except tk.TclError:
                pass   # canvas destroyed — stop silently

        # Seed with a few bursts so something is visible immediately
        for _ in range(5):
            launch()
        tick()

    def _stop_fireworks(self):
        self._fw_running = False
        if self._fw_after_id is not None:
            try:
                self.after_cancel(self._fw_after_id)
            except Exception:
                pass
            self._fw_after_id = None
        self._fw_particles = []

    # =========================================================================
    # RESTART
    # =========================================================================

    def _confirm_restart(self):
        from tkinter import messagebox
        if messagebox.askyesno(
            "Restart Game",
            "Start a brand-new game?  Current progress will be lost.",
        ):
            self._build_start_screen()

    # =========================================================================
    # RULES POPUP
    # =========================================================================

    def _show_rules(self):
        win = tk.Toplevel(self)
        win.title("Rules Summary — DeepCarb Planner")
        win.configure(bg=THEME["bg_dark"])
        win.geometry("600x520")

        text_widget = tk.Text(
            win, font=FONTS["small"], bg=THEME["bg_code"], fg="#ccc",
            wrap="word", padx=12, pady=10, relief="flat",
        )
        text_widget.pack(fill="both", expand=True)
        text_widget.insert("end", RULES_TEXT)
        text_widget.config(state="disabled")

    # =========================================================================
    # HELPER
    # =========================================================================

    def _clear_window(self):
        self._stop_fireworks()
        for w in self.winfo_children():
            w.destroy()


# ─── Rules text ───────────────────────────────────────────────────────────────
# Edit this string to update the in-game help text.

RULES_TEXT = """\
DEEPCARB PLANNER — Rules Summary
=================================

GOAL
Earn the most points by fulfilling production orders using renewable energy.

SETUP (per player)
• 1 factory planner (5 days × 6 slots)
• 1 battery tile in storage (max 5)
• Priority tokens 1–4 decide turn order

EACH DAY (Mon–Fri)
I. Assign priorities based on energy need already in this day's column (highest = first).

II. Work Phase (repeat until day ends):
  On your turn you do TWO actions in order:
  1. REVEAL — flip one weather tile on today's card face-up.
  2. CHOOSE one of:
       A) BUY ENERGY    — take any tile from today's card, place in today's column.
       B) TAKE ORDER    — take an order from the display, place horizontally
                          across free slots (current or future days only).
       C) PASS          — skip the optional second action.

  Day ends when: all positive energy tiles are taken, or everyone passes.
  After the last tile is taken, every other player gets one more optional action.

III. End of Day — Energy Balance
  needed   = sum of red ⚡ on your orders in today's column
  available = sum of yellow ⚡ on your energy tiles in today's column
  balance  = available − needed

  Surplus  → store as battery tiles (capped at 5)
  Deficit  → spend batteries first, then buy conventional energy (−2 pts each)
  ♻ symbol → each ♻ order grants +1 battery at end of that day (if storage not full)

ENERGY TYPES
  ☀ Sun:   avg 2, σ 1   (may produce 0 = cloud)
  💨 Wind:  avg 2.5, σ 1.5  (may produce 0 = calm)
  💧 Water: avg 1.5, σ 0.5  (no zero tiles)

ORDERS
  Duration 1 / 2 / 3 days — must be placed in consecutive future day columns.
  Energy needed per day shown in red.  Victory points shown on the tile.
  3-day orders cannot start on Thursday or Friday.
  2-day orders cannot start on Friday.

SCORING (end of Friday)
  + Points printed on completed orders
  + Battery bonus: ≥2 = 1 pt,  ≥4 = 2 pts,  ≥5 = 3 pts
  − Conventional energy: 2 pts per tile purchased
  Tiebreaker: highest battery storage wins.
"""

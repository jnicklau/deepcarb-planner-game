"""
engine.py — DeepCarb Planner
=============================
Pure game logic: no tkinter imports, no UI concerns.
Depends only on config.py and the standard library.
"""

import random
import copy

from config import (
    DAYS, ROWS_PER_DAY, BATTERY_CAPACITY, STARTING_BATTERIES,
    BATTERY_BONUS, CONV_ENERGY_PENALTY,
    WEATHER_POOL, WEATHER_TILES_MIN, WEATHER_TILES_MAX,
    ORDER_TEMPLATES, ORDERS_PER_SLOT_SMALL, ORDERS_PER_SLOT_LARGE,
    MAX_ORDER_DURATION_BY_DAY,
    PLAYER_COLORS, PLAYER_COLOR_NAMES,
)


# ─── Weather ──────────────────────────────────────────────────────────────────

class WeatherCard:
    """One day's set of weather tiles, each face-up or face-down."""

    def __init__(self, tiles: list[dict]):
        # tile = {"type": str, "value": int, "revealed": bool, "on_card": bool}
        self.tiles = tiles

    # Convenience queries ──────────────────────────────────────────────────────

    def on_card(self) -> list[dict]:
        """All tiles not yet taken by any player."""
        return [t for t in self.tiles if t["on_card"]]

    def revealed_on_card(self) -> list[dict]:
        return [t for t in self.on_card() if t["revealed"]]

    def hidden_on_card(self) -> list[dict]:
        return [t for t in self.on_card() if not t["revealed"]]

    def has_positive_energy(self) -> bool:
        """True if at least one remaining tile has energy value > 0."""
        return any(t["value"] > 0 for t in self.on_card())


def _make_weather_cards(num_players: int) -> list["WeatherCard"]:
    """
    Draw tiles without replacement from WEATHER_POOL for every day of the week.
    Each day gets randint(WEATHER_TILES_MIN, WEATHER_TILES_MAX) * num_players tiles.
    If the total required exceeds the pool size, retry until a feasible draw is found.
    The first tile of each day is revealed face-up; the rest start face-down.
    """
    pool = list(WEATHER_POOL)
    while True:
        counts = [
            random.randint(WEATHER_TILES_MIN, WEATHER_TILES_MAX) * num_players
            for _ in DAYS
        ]
        if sum(counts) > len(pool):
            continue  # retry — total exceeds available tiles
        random.shuffle(pool)
        cards = []
        i = 0
        for count in counts:
            tiles = [
                {"type": t, "value": v, "revealed": False, "on_card": True}
                for t, v in pool[i: i + count]
            ]
            if tiles:
                tiles[0]["revealed"] = True   # first tile face-up
            cards.append(WeatherCard(tiles))
            i += count
        return cards


# ─── Player ───────────────────────────────────────────────────────────────────

class Player:
    def __init__(self, name: str, color_idx: int):
        self.name = name
        self.color = PLAYER_COLORS[color_idx]
        self.color_name = PLAYER_COLOR_NAMES[color_idx]
        # factory_planner[day_idx][row] = tile dict | None
        self.factory_planner: list[list[dict | None]] = [
            [None] * ROWS_PER_DAY for _ in range(len(DAYS))
        ]
        self.battery_storage: int = STARTING_BATTERIES
        self.conventional_energy: int = 0
        self.priority: int = color_idx + 1

    # ── Factory planner helpers ────────────────────────────────────────────────

    def tiles_in_day(self, day: int) -> list[dict]:
        return [t for t in self.factory_planner[day] if t is not None]

    def energy_in_day(self, day: int) -> int:
        return sum(t["value"] for t in self.tiles_in_day(day) if t["type"] == "energy")

    def energy_needed_day(self, day: int) -> int:
        return sum(t["energy"] for t in self.tiles_in_day(day) if t["type"] == "order")

    def energy_recovery_day(self, day: int) -> int:
        return sum(
            1 for t in self.tiles_in_day(day)
            if t["type"] == "order" and t.get("recovery")
        )

    def free_slots_day(self, day: int) -> int:
        return sum(1 for t in self.factory_planner[day] if t is None)

    def first_free_row(self, day: int) -> int | None:
        for r, t in enumerate(self.factory_planner[day]):
            if t is None:
                return r
        return None

    def first_shared_free_row(self, start_day: int, dur: int) -> int | None:
        """Find the first row index that is empty in every day column of the order span."""
        for r in range(ROWS_PER_DAY):
            if all(self.factory_planner[d][r] is None for d in range(start_day, start_day + dur)):
                return r
        return None

    # ── Scoring ───────────────────────────────────────────────────────────────

    def compute_score(self) -> int:
        return sum(self.score_breakdown().values())

    def score_breakdown(self) -> dict[str, int]:
        """Return individual scoring components as a dict."""
        order_pts = 0
        for day in range(len(DAYS)):
            for tile in self.factory_planner[day]:
                if tile and tile["type"] == "order":
                    last_day = tile["start_day"] + tile["total_days"] - 1
                    if day == last_day:
                        order_pts += tile["points"]

        battery_bonus = 0
        for threshold in sorted(BATTERY_BONUS.keys(), reverse=True):
            if self.battery_storage >= threshold:
                battery_bonus = BATTERY_BONUS[threshold]
                break

        co2_penalty = -(self.conventional_energy * CONV_ENERGY_PENALTY)

        total_energy = sum(
            tile["value"]
            for day in range(len(DAYS))
            for tile in self.factory_planner[day]
            if tile and tile["type"] == "energy"
        )

        return {
            "order_pts":    order_pts,
            "battery_bonus": battery_bonus,
            "co2_penalty":  co2_penalty,
            "total_energy": total_energy,
        }


# ─── Game Engine ──────────────────────────────────────────────────────────────

class GameEngine:
    def __init__(self, player_names: list[str]):
        self.players = [Player(n, i) for i, n in enumerate(player_names)]
        self.num_players = len(player_names)
        self.current_day: int = 0
        self.current_player_idx: int = 0
        self.turn_order: list[int] = list(range(self.num_players))

        self.weather_cards = _make_weather_cards(self.num_players)
        self.order_deck: list[dict] = self._make_order_deck()
        self.order_display: list[dict] = []
        self._fill_order_display()

        # "reveal"  – player must flip a weather tile first
        # "action"  – player may buy energy / take order / pass
        self.action_state: str = "reveal"
        self.day_ended: bool = False
        self.game_over: bool = False
        self.log_messages: list[str] = []
        # Filled at end of each day; cleared by UI after it displays the summary
        self.day_summary: dict | None = None

    # ── Setup helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _make_order_deck() -> list[dict]:
        deck = copy.deepcopy(ORDER_TEMPLATES)
        random.shuffle(deck)
        return deck

    def _fill_order_display(self):
        per_slot = ORDERS_PER_SLOT_LARGE if self.num_players >= 3 else ORDERS_PER_SLOT_SMALL
        max_dur = MAX_ORDER_DURATION_BY_DAY.get(self.current_day, 3)
        allowed_durations = [d for d in (1, 2, 3) if d <= max_dur]

        self.order_display = []
        for dur in allowed_durations:
            count = 0
            for order in self.order_deck[:]:
                if order["duration"] == dur and count < per_slot:
                    self.order_display.append(order)
                    self.order_deck.remove(order)
                    count += 1

    def _refresh_order_display(self):
        """Discard current display, return tiles to deck, draw fresh ones."""
        self.order_deck.extend(self.order_display)
        random.shuffle(self.order_deck)
        self.order_display = []
        self._fill_order_display()

    # ── Accessors ─────────────────────────────────────────────────────────────

    def current_player(self) -> Player:
        return self.players[self.turn_order[self.current_player_idx]]

    def weather_card(self) -> WeatherCard:
        return self.weather_cards[self.current_day]

    def log(self, msg: str):
        self.log_messages.append(msg)
        if len(self.log_messages) > 100:
            self.log_messages = self.log_messages[-100:]

    def pool_stats(self) -> dict[str, dict[int, tuple[int, int]]]:
        """
        Return usage stats against the FULL WEATHER_POOL (all copies).
        Result: { type: { value: (total_in_full_pool, used_this_game) } }
        where 'used' = revealed or collected across all drawn weather cards.
        """
        # Totals from the entire configured pool (not just this game's draw)
        totals: dict[str, dict[int, int]] = {}
        for t, v in WEATHER_POOL:
            totals.setdefault(t, {}).setdefault(v, 0)
            totals[t][v] += 1

        # Used = revealed or taken, from the cards actually drawn this game
        used: dict[str, dict[int, int]] = {}
        for wc in self.weather_cards:
            for tile in wc.tiles:
                t, v = tile["type"], tile["value"]
                used.setdefault(t, {}).setdefault(v, 0)
                if tile["revealed"] or not tile["on_card"]:
                    used[t][v] += 1

        result = {}
        for t in totals:
            result[t] = {
                v: (totals[t][v], min(used.get(t, {}).get(v, 0), totals[t][v]))
                for v in totals[t]
            }
        return result

    # ── Player actions ────────────────────────────────────────────────────────

    def do_reveal_tile(self, tile: dict):
        """Mandatory first action: flip one weather tile face-up."""
        tile["revealed"] = True
        self.log(
            f"{self.current_player().name} reveals a "
            f"{tile['type']} tile: {tile['value']} energy"
        )
        self.action_state = "action"

    def do_buy_energy(self, tile: dict) -> bool:
        """Take an energy tile from the weather card and place it in today's column."""
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
        self.log(f"{player.name} collects {tile['type']} energy: +{tile['value']}")
        self._check_day_end_trigger()
        self._advance_turn()
        return True

    def do_take_order(self, order: dict, start_day: int) -> bool:
        """Place an order starting at start_day, spanning order['duration'] days."""
        player = self.current_player()
        dur = order["duration"]
        row = player.first_shared_free_row(start_day, dur)
        if row is None:
            self.log("Not enough space for this order!")
            return False

        for d in range(start_day, start_day + dur):
            offset = d - start_day
            player.factory_planner[d][row] = {
                "type":            "order",
                "duration":        dur,
                "energy":          order["energy"],
                "points":          order["points"],
                "recovery":        offset in order.get("recovery", []),
                "recovery_offsets": list(order.get("recovery", [])),
                "start_day":       start_day,
                "day_offset":      offset,
                "total_days":      dur,
            }

        if order in self.order_display:
            self.order_display.remove(order)

        self.log(
            f"{player.name} takes a {dur}-day order "
            f"({order['energy']} ⚡/day, {order['points']} pts)"
        )
        self._advance_turn()
        return True

    def do_pass(self):
        """Skip the optional second action."""
        self.log(f"{self.current_player().name} passes")
        self._advance_turn()

    def force_end_of_day(self):
        """Manually trigger end-of-day (e.g. via UI button)."""
        self.day_ended = True
        self._end_of_day()

    # ── Internal turn flow ────────────────────────────────────────────────────

    def _check_day_end_trigger(self):
        if not self.weather_card().has_positive_energy():
            self.log("Last positive energy tile taken — end of work day!")
            self.day_ended = True

    def _advance_turn(self):
        # If all remaining tiles on today's card are already revealed, skip the reveal step
        if self.weather_card().hidden_on_card():
            self.action_state = "reveal"
        else:
            self.action_state = "action"
        self.current_player_idx = (self.current_player_idx + 1) % self.num_players
        if self.day_ended and self.current_player_idx == 0:
            self._end_of_day()

    def _end_of_day(self):
        day = self.current_day
        self.log(f"=== End of {DAYS[day]} ===")
        player_summaries = []
        for player in self.players:
            ps = self._resolve_energy_balance(player)
            player_summaries.append(ps)
        self.day_summary = {"day": day, "day_name": DAYS[day], "players": player_summaries}
        self._refresh_order_display()
        self.current_day += 1
        if self.current_day >= len(DAYS):
            self._end_game()
        else:
            self.day_ended = False
            self.current_player_idx = 0
            self.action_state = "reveal"   # every new day starts with a mandatory reveal
            self._assign_priorities()
            # Attach next-day info to the summary so the UI can display it
            self.day_summary["next_day"] = DAYS[self.current_day]
            self.day_summary["next_day_order"] = [self.players[i] for i in self.turn_order]
            self.log(f"=== Start of {DAYS[self.current_day]} ===")

    def _resolve_energy_balance(self, player: Player) -> dict:
        """Resolve end-of-day energy balance and return a summary dict."""
        day = self.current_day
        available = player.energy_in_day(day)
        needed    = player.energy_needed_day(day)
        balance   = available - needed
        recovery  = player.energy_recovery_day(day)

        batteries_used = 0
        batteries_stored = 0
        conv_bought = 0
        recovered = 0

        if balance >= 0:
            batteries_stored = min(balance, BATTERY_CAPACITY - player.battery_storage)
            player.battery_storage += batteries_stored
            self.log(f"{player.name}: +{balance} surplus → stored {batteries_stored} batteries")
        else:
            deficit = -balance
            batteries_used = min(deficit, player.battery_storage)
            player.battery_storage -= batteries_used
            deficit -= batteries_used
            if deficit > 0:
                conv_bought = deficit
                player.conventional_energy += conv_bought
                self.log(
                    f"{player.name}: bought {conv_bought} conventional energy "
                    f"(−{conv_bought * CONV_ENERGY_PENALTY} pts)"
                )
            else:
                self.log(f"{player.name}: used {batteries_used} batteries to cover deficit")

        if recovery > 0:
            recovered = min(recovery, BATTERY_CAPACITY - player.battery_storage)
            player.battery_storage += recovered
            self.log(f"{player.name}: recovered {recovered} energy from orders ♻")

        return {
            "player":           player,
            "available":        available,
            "needed":           needed,
            "balance":          balance,
            "batteries_used":   batteries_used,
            "batteries_stored": batteries_stored,
            "conv_bought":      conv_bought,
            "recovered":        recovered,
            "battery_total":    player.battery_storage,
        }

    def _assign_priorities(self):
        day = self.current_day
        ranked = sorted(
            range(self.num_players),
            key=lambda i: -self.players[i].energy_needed_day(day)
        )
        self.turn_order = ranked
        self.current_player_idx = 0
        names = [self.players[i].name for i in self.turn_order]
        self.log(f"Turn order for {DAYS[day]}: {', '.join(names)}")

    def _end_game(self):
        self.game_over = True
        self.log("=== GAME OVER ===")
        for p in self.players:
            self.log(f"{p.name}: {p.compute_score()} points")

    # ── Queries used by the UI ─────────────────────────────────────────────────

    def allowed_start_days(self, player: Player, order: dict) -> list[int]:
        """Return day indices where the player can legally start this order."""
        dur = order["duration"]
        return [
            d for d in range(self.current_day, len(DAYS) - dur + 1)
            if player.first_shared_free_row(d, dur) is not None
        ]

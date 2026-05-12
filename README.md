# DeepCarb Planner

A digital companion for the **DeepCarb Planner** board game developed at HTWG Konstanz.  
2–4 players plan a factory's energy supply across a 5-day work week using renewable sources
(solar, wind, hydro), batteries, and production orders.

## Features

- Full game logic for 2–4 players
- Weather tile tableau with day-by-day reveal mechanic
- Scrollable factory planners per player with multi-day order tiles
- Energy pool histograms and game log
- End-of-day summary popup (scrollable) with next-day turn order
- End screen with fireworks, score breakdown, and full game tableau view
- Keyboard shortcuts for fast play

## Requirements

- Python 3.10+
- Tkinter (included in the standard library on most Python installations)

No third-party packages are required.

## Installation

```bash
# Clone the repository
git clone https://github.com/<your-username>/deepcarb-planner.git
cd deepcarb-planner

# (Optional) create and activate a virtual environment
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate
```

## Running the game

```bash
python run.py
```

## Project structure

```
game_ui_ai/
├── run.py        # Entry point — just launches the app
├── ui.py         # All tkinter UI code
├── engine.py     # Game logic (no UI imports)
├── config.py     # Game data, theme, fonts, icons
└── README.md
```

## Keyboard shortcuts (in-game)

| Key | Action |
|-----|--------|
| `1`–`9` | Interact with the Nth visible weather tile |
| `Q`–`O` | Select order 1–9 from the display |
| `Space` / `P` | Pass your action |
| `D` | Force end of day |
| `↑` / `↓` + `Enter` | Navigate / confirm the day-picker dialog |
| `Enter` | Dismiss the end-of-day summary |

## License

This project is licensed under the **Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)** license.

You are free to:
- **Use** and **share** this project for personal, educational, or research purposes
- **Adapt** or build upon it

Under the following conditions:
- **Attribution** — You must give appropriate credit and link to this repository
- **NonCommercial** — You may **not** use this project or its concepts for commercial purposes

> © 2026 HTWG Konstanz. All commercial rights reserved.

Full license text: https://creativecommons.org/licenses/by-nc/4.0/

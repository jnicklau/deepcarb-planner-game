import re
content = open("ui.py", encoding="utf-8").read()
old = "            tiles = self.engine.weather_card().tiles\n"
new = '            tiles = [t for t in self.engine.weather_card().tiles if t["on_card"]]\n'
if old in content:
    open("ui.py", "w", encoding="utf-8").write(content.replace(old, new, 1))
    print("done")
else:
    print("not found")

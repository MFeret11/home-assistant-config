"""
PC window checks.

sensor.gaming_pc_active_game (the "Gaming PC Active Game" template in
configuration.yaml) and pyscript/modules/pc_window.py both decide which PC windows
aren't games. This fails if their lists differ, and checks windows the PC has
really reported.

Run: python3 tests/test_pc_window.py
"""
import ast
import os
import re
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(REPO, "pyscript", "modules"))
import theater_art  # noqa: E402,F401  (pc_window imports its title regexes)
import pc_window  # noqa: E402


def template_lists():
    """The suffix list and the exact-name list from the Gaming PC Active Game template."""
    text = open(os.path.join(REPO, "configuration.yaml")).read()
    block = text[text.index('name: "Gaming PC Active Game"'):]
    block = block[:block.index("Steam Big Picture\n")]
    suffixes = re.search(r"{% for s in (\[.*?\]) %}", block, re.S).group(1)
    names = re.search(r"{% if ns\.app or low in (\[.*?\]) %}", block, re.S).group(1)
    return ast.literal_eval(suffixes), ast.literal_eval(names)


def main():
    failures = []
    suffixes, names = template_lists()
    if suffixes != pc_window.NOT_GAME_SUFFIXES:
        failures.append(f"NOT_GAME_SUFFIXES differs from the template: "
                        f"only in template {sorted(set(suffixes) - set(pc_window.NOT_GAME_SUFFIXES))}, "
                        f"only in pc_window.py {sorted(set(pc_window.NOT_GAME_SUFFIXES) - set(suffixes))}")
    ours = pc_window.NOT_GAME_WINDOWS - {"idle / desktop"}
    if set(names) != ours:
        failures.append(f"NOT_GAME_WINDOWS differs from the template: "
                        f"only in template {sorted(set(names) - ours)}, only in pc_window.py {sorted(ours - set(names))}")

    expected = {
        # Windows the PC has reported that aren't games
        "Idle / Desktop": "desktop", "Visual Studio Code": "desktop", "Voice access": "desktop",
        "Search": "desktop", "Quick settings": "desktop", "System tray overflow window.": "desktop",
        "Discord": "desktop", "notes.txt - Notepad": "desktop", "Inbox - Outlook": "desktop",
        "Steam Big Picture": "idle", "steam": "idle",
        None: "off", "unavailable": "off",
        # Games
        "Elden Ring": "playing", "Cyberpunk 2077 (C) 2020 by CD Projekt RED": "playing", "ApeOut": "playing",
    }
    for window, want in expected.items():
        got = pc_window.parse_pc_active_window(window)[1]
        if got != want:
            failures.append(f"{window!r} reads as {got!r}, expected {want!r}")

    if failures:
        print("FAIL: PC window lists")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print(f"PASS: template and pc_window.py agree ({len(names)} names, {len(suffixes)} endings); "
          f"{len(expected)} sample windows read correctly")


if __name__ == "__main__":
    main()

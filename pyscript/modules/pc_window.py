# ==============================================================================
# PC WINDOW: is the gaming PC running a game?
# ==============================================================================
# HASS.Agent on the PC reports the foreground window. The "Gaming PC Active Game"
# template in configuration.yaml turns it into sensor.gaming_pc_active_game: a game
# title, "Steam Big Picture", or "Idle / Desktop" for anything that isn't a game.
# parse_pc_active_window() reads that sensor for theater.py (the game poster) and
# basement.py (lights go dark while a game is playing).
#
# The two "not a game" lists below are the same lists as that template, checked
# again here in case a raw window name gets through. To add a window, add it in
# both places; tests/test_pc_window.py fails if they differ.
#
# Saving this file reloads theater.py and basement.py, so edit it with the theater idle.
# ==============================================================================
import re

from theater_art import RE_ROM_EXT, RE_ROM_TAGS

# Window names that aren't games (compared in lowercase)
NOT_GAME_WINDOWS = {
    "", "unknown", "unavailable", "none", "null", "undefined",
    "desktop", "task switching", "taskbar", "explorer", "start",
    "windows shell experience host", "program manager", "home assistant",
    "hass.agent", "settings", "calculator", "task manager", "device manager",
    "command prompt", "powershell", "terminal", "notepad", "discord",
    "spotify", "spotify free", "spotify premium",
    "visual studio code", "voice access", "search", "quick settings",
    "system tray overflow window.",
    "idle / desktop",  # what the template reports for all of the above
}

# Window title endings that mean an app, not a game ("Inbox - Outlook")
NOT_GAME_SUFFIXES = [
    "- google chrome", "- microsoft edge", "- mozilla firefox", "- brave",
    "- visual studio code", "- desktop viewer", "- citrix workspace",
    "- home assistant", "- file explorer", "- notepad", "- notepad++",
    "- word", "- excel", "- powerpoint", "- outlook", "- microsoft teams",
    "- slack", "- discord", "- obsidian",
]

# Version and copyright clutter in game window titles
RE_PC_CLEANUP = re.compile(
    r"\s*(?:\(x(?:64|86)\)|\[DirectX\s*\d*\]|\(DX\d+\)|v\d+(?:\.\d+)+|build\s*\d+|™|®|\(C\).*?$)",
    re.IGNORECASE
)


def parse_pc_active_window(raw_window):
    """Read sensor.gaming_pc_active_game. Returns (game_title, state, is_steam), where
    state is "playing" (in a game), "idle" (Steam Big Picture), "desktop" (not a
    game) or "off" (no window reported)."""
    if not raw_window or str(raw_window).strip() in ["", "none", "None", "unknown", "unavailable"]:
        return ("", "off", False)

    w = str(raw_window).strip()
    w_lower = w.lower()

    if w_lower in NOT_GAME_WINDOWS or any([w_lower.endswith(s) for s in NOT_GAME_SUFFIXES]):
        return ("", "desktop", False)

    if "steam big picture" in w_lower or w_lower == "steam":
        return ("Steam Big Picture Mode", "idle", True)

    clean = RE_ROM_EXT.sub("", w)
    clean = RE_ROM_TAGS.sub("", clean)
    clean = RE_PC_CLEANUP.sub("", clean).strip()

    if not clean or clean.lower() in NOT_GAME_WINDOWS:
        return ("", "desktop", False)

    return (clean, "playing", False)

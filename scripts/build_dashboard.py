#!/usr/bin/env python3
"""
Home Assistant dashboard checker.
Checks that dashboards/basement.yaml and its components line up. Read-only:
basement.yaml is hand-maintained and this script never writes to it.

Usage:
  python3 scripts/build_dashboard.py                    # check basement.yaml includes
  python3 scripts/build_dashboard.py --test             # check, then run the full test suite
  python3 scripts/build_dashboard.py --monolith OUT     # also write an inlined copy to OUT
"""
import os
import sys
import argparse
import re
import subprocess
from typing import Dict, List, Any, Optional

# Add tests directory to path to reuse entity registry
TESTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tests"))
sys.path.insert(0, TESTS_DIR)
try:
    from test_dashboard_integrity import REGISTERED_ENTITIES, REGISTERED_SERVICES
except ImportError:
    REGISTERED_ENTITIES = set()
    REGISTERED_SERVICES = set()

# ------------------------------------------------------------------------------
# 1. LOVELACE COMPONENT BUILDERS (TYPE-SAFE PYTHON DSL)
# ------------------------------------------------------------------------------
class LovelaceBuilder:
    """Helper methods for generating clean, validated Home Assistant Lovelace card configs."""

    @staticmethod
    def validate_entity(entity_id: str):
        """Validate entity against registered dictionary."""
        if REGISTERED_ENTITIES and entity_id and "." in entity_id:
            if not entity_id.startswith("[[") and entity_id not in REGISTERED_ENTITIES:
                print(f"  [WARNING] Unregistered entity detected: '{entity_id}'")

    @staticmethod
    def bubble_slider(
        entity: str,
        name: str,
        icon: str,
        sub_buttons: Optional[List[Dict[str, Any]]] = None,
        card_mod: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate a Bubble Card slider."""
        LovelaceBuilder.validate_entity(entity)
        card: Dict[str, Any] = {
            "type": "custom:bubble-card",
            "card_type": "button",
            "button_type": "slider",
            "entity": entity,
            "name": name,
            "icon": icon,
            "show_state": True,
        }
        if sub_buttons:
            card["sub_button"] = sub_buttons
        if card_mod:
            card["card_mod"] = {"style": card_mod.strip()}
        return card

    @staticmethod
    def bubble_popup(
        hash_tag: str,
        name: str,
        icon: str,
        cards: List[Dict[str, Any]],
        bg_color: str = "rgba(10, 15, 26, 0.96)",
        bg_blur: int = 24,
        shadow_opacity: float = 0.8
    ) -> Dict[str, Any]:
        """Generate a Standalone Bubble Card v3.2.0+ Pop-up modal."""
        return {
            "type": "custom:bubble-card",
            "card_type": "pop-up",
            "hash": hash_tag if hash_tag.startswith("#") else f"#{hash_tag}",
            "name": name,
            "icon": icon,
            "show_header": True,
            "bg_color": bg_color,
            "bg_blur": bg_blur,
            "shadow_opacity": shadow_opacity,
            "cards": cards,
        }

    @staticmethod
    def mushroom_template(
        primary: str,
        secondary: Optional[str] = None,
        icon: Optional[str] = None,
        icon_color: Optional[str] = None,
        layout: str = "horizontal",
        tap_action: Optional[Dict[str, Any]] = None,
        hold_action: Optional[Dict[str, Any]] = None,
        card_mod: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate a Mushroom Template card."""
        card: Dict[str, Any] = {
            "type": "custom:mushroom-template-card",
            "primary": primary,
            "layout": layout,
        }
        if secondary:
            card["secondary"] = secondary
        if icon:
            card["icon"] = icon
        if icon_color:
            card["icon_color"] = icon_color
        if tap_action:
            card["tap_action"] = tap_action
        if hold_action:
            card["hold_action"] = hold_action
        if card_mod:
            card["card_mod"] = {"style": card_mod.strip()}
        return card

    @staticmethod
    def mushroom_chips(
        chips: List[Dict[str, Any]],
        alignment: str = "start",
        card_mod: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate a Mushroom Chips container."""
        res: Dict[str, Any] = {
            "type": "custom:mushroom-chips-card",
            "alignment": alignment,
            "chips": chips,
        }
        if card_mod:
            res["card_mod"] = {"style": card_mod.strip()}
        return res

    @staticmethod
    def chip_template(
        icon: str,
        content: Optional[str] = None,
        icon_color: Optional[str] = None,
        tap_action: Optional[Dict[str, Any]] = None,
        card_mod: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate an individual chip."""
        chip: Dict[str, Any] = {
            "type": "template",
            "icon": icon,
        }
        if content:
            chip["content"] = content
        if icon_color:
            chip["icon_color"] = icon_color
        if tap_action:
            chip["tap_action"] = tap_action
        if card_mod:
            chip["card_mod"] = {"style": card_mod.strip()}
        return chip

    @staticmethod
    def decluttering(template_name: str, variables: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Generate a Decluttering card reference."""
        res: Dict[str, Any] = {
            "type": "custom:decluttering-card",
            "template": template_name,
        }
        if variables:
            res["variables"] = variables
        return res

    @staticmethod
    def conditional(conditions: List[Dict[str, Any]], card: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a Conditional card wrapper."""
        return {
            "type": "conditional",
            "conditions": conditions,
            "card": card,
        }

    @staticmethod
    def vertical_stack(cards: List[Dict[str, Any]], card_mod: Optional[str] = None) -> Dict[str, Any]:
        """Generate a Vertical Stack card."""
        res: Dict[str, Any] = {
            "type": "vertical-stack",
            "cards": cards,
        }
        if card_mod:
            res["card_mod"] = {"style": card_mod.strip()}
        return res

    @staticmethod
    def horizontal_stack(cards: List[Dict[str, Any]], card_mod: Optional[str] = None) -> Dict[str, Any]:
        """Generate a Horizontal Stack card."""
        res: Dict[str, Any] = {
            "type": "horizontal-stack",
            "cards": cards,
        }
        if card_mod:
            res["card_mod"] = {"style": card_mod.strip()}
        return res

    @staticmethod
    def grid(cards: List[Dict[str, Any]], columns: int = 3, square: bool = True) -> Dict[str, Any]:
        """Generate a Grid card."""
        return {
            "type": "grid",
            "square": square,
            "columns": columns,
            "cards": cards,
        }


# ------------------------------------------------------------------------------
# 2. DASHBOARD ORCHESTRATION & COMPILATION
# ------------------------------------------------------------------------------
COMPONENTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "dashboards", "components"))
DASHBOARDS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "dashboards"))

BASEMENT_PATH = os.path.join(DASHBOARDS_DIR, "basement.yaml")
INCLUDE_RE = re.compile(r"^(?P<indent>\s*)(?P<prefix>- |[\w-]+: )!include (?P<path>\S+)\s*$")


def check_basement():
    """Read-only check: basement.yaml's !includes all exist and every component is used.

    basement.yaml is hand-maintained and is the source of truth for the layout.
    This never writes to it.
    """
    with open(BASEMENT_PATH, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()

    included = set()
    problems = []
    for n, line in enumerate(lines, 1):
        m = INCLUDE_RE.match(line)
        if not m:
            continue
        rel = m.group("path")
        included.add(os.path.normpath(rel))
        if not os.path.isfile(os.path.join(DASHBOARDS_DIR, rel)):
            problems.append(f"basement.yaml:{n} includes missing file {rel}")

    for name in sorted(os.listdir(COMPONENTS_DIR)):
        rel = os.path.normpath(os.path.join("components", name))
        if name.endswith(".yaml") and rel not in included:
            problems.append(f"{rel} is not included by basement.yaml")

    for p in problems:
        print(f"  ✗ {p}")
    if not problems:
        print(f"  ✓ basement.yaml: {len(included)} includes, all present, no orphan components")
    return not problems


def build_monolithic_basement(out_path: str):
    """Inline basement.yaml's !includes into one standalone file at out_path.

    Follows the real basement.yaml layout. Refuses to write inside dashboards/,
    since every file there is a live, registered dashboard.
    """
    out_abs = os.path.abspath(out_path)
    if os.path.commonpath([out_abs, DASHBOARDS_DIR]) == DASHBOARDS_DIR:
        sys.exit(f"Refusing to write {out_abs}: dashboards/ files are live. Pick a path outside it.")

    def read_comp(rel):
        with open(os.path.join(DASHBOARDS_DIR, rel), "r", encoding="utf-8") as f:
            return f.read().rstrip("\n").splitlines()

    with open(BASEMENT_PATH, "r", encoding="utf-8") as f:
        src = f.read().splitlines()

    out = []
    for line in src:
        m = INCLUDE_RE.match(line)
        if not m:
            out.append(line)
            continue
        indent, prefix = m.group("indent"), m.group("prefix")
        body = read_comp(m.group("path"))
        if prefix == "- ":
            # List item: first line follows the dash, the rest align under it.
            pad = indent + "  "
            out.append(indent + "- " + body[0])
            out.extend(pad + l if l.strip() else "" for l in body[1:])
        else:
            # Mapping key: nest the file's content one level under the key.
            pad = indent + "  "
            out.append(indent + prefix.rstrip())
            out.extend(pad + l if l.strip() else "" for l in body)

    with open(out_abs, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    print(f"  ✓ Compiled monolith: {out_abs} ({len(out)} lines)")

def run_tests():
    """Runs test harness to verify output."""
    test_script = os.path.join(TESTS_DIR, "run_all_tests.py")
    print("\n▶ Running full verification test suite...")
    res = subprocess.run([sys.executable, test_script])
    return res.returncode == 0

def main():
    parser = argparse.ArgumentParser(description="Home Assistant Dashboard-as-Code Builder")
    parser.add_argument("--monolith", metavar="OUT", help="Also write a single inlined YAML file to OUT (outside dashboards/)")
    parser.add_argument("--test", action="store_true", help="Run full automated verification test suite")
    args = parser.parse_args()

    print("==================================================")
    print("BASEMENT DASHBOARD CHECK (read-only)")
    print("==================================================")

    ok = check_basement()
    if args.monolith:
        build_monolithic_basement(args.monolith)
    if args.test:
        ok = run_tests() and ok
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()

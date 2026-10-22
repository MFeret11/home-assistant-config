#!/usr/bin/env python3
"""
Home Assistant Dashboard-as-Code Compiler & Builder
Builds, validates, and manages Home Assistant Lovelace dashboards programmatically.

Usage:
  python3 scripts/build_dashboard.py             # Build and validate all components
  python3 scripts/build_dashboard.py --test      # Build and run the test harness
  python3 scripts/build_dashboard.py --monolith  # Output a single unified YAML file
"""
import os
import sys
import argparse
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

def build_modular_basement():
    """Generates the master modular basement.yaml leveraging component includes."""
    target_path = os.path.join(DASHBOARDS_DIR, "basement.yaml")
    content = """title: Basement
decluttering_templates: !include components/decluttering_templates.yaml

views:
  - title: Basement
    path: basement
    icon: mdi:home-floor-b
    type: sections
    max_columns: 2
    sections:
      # =========================================================
      # SECTION 1: HEADER & DUAL-AUDIO COCKPIT
      # =========================================================
      - type: grid
        cards:
          - !include components/header_cockpit_chips.yaml
          - !include components/header_avr_volume.yaml
          - !include components/header_booth_announcer.yaml

      # =========================================================
      # SECTION 2: CINEMA, SPORTS & ARCADE EXPERIENCE
      # =========================================================
      - type: grid
        cards:
          - !include components/now_playing_marquee.yaml
          - !include components/eagles_team_tracker.yaml
          - !include components/theater_stage.yaml
          - !include components/zone_lighting.yaml
          - !include components/theater_remote_popup.yaml
"""
    with open(target_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  ✓ Built modular master: {target_path} (30 lines)")

def build_monolithic_basement():
    """Compiles all components into a single standalone monolithic basement.yaml."""
    target_path = os.path.join(DASHBOARDS_DIR, "basement.yaml")
    
    # Read each component
    def read_comp(name):
        p = os.path.join(COMPONENTS_DIR, name)
        with open(p, "r", encoding="utf-8") as f:
            return f.read()

    def indent(text, spaces):
        sp = " " * spaces
        lines = []
        for line in text.splitlines():
            lines.append(sp + line if line.strip() else "")
        return "\n".join(lines)

    decluttering = indent(read_comp("decluttering_templates.yaml"), 2)
    chips = indent("- " + read_comp("header_cockpit_chips.yaml").lstrip(), 10)
    avr_vol = indent("- " + read_comp("header_avr_volume.yaml").lstrip(), 10)
    announcer = indent("- " + read_comp("header_booth_announcer.yaml").lstrip(), 10)
    marquee = indent("- " + read_comp("now_playing_marquee.yaml").lstrip(), 10)
    eagles = indent("- " + read_comp("eagles_team_tracker.yaml").lstrip(), 10)
    stage = indent("- " + read_comp("theater_stage.yaml").lstrip(), 10)
    lighting = indent("- " + read_comp("zone_lighting.yaml").lstrip(), 10)
    popup = indent("- " + read_comp("theater_remote_popup.yaml").lstrip(), 10)

    monolith = f"""title: Basement
decluttering_templates:
{decluttering}

views:
  - title: Basement
    path: basement
    icon: mdi:home-floor-b
    type: sections
    max_columns: 2
    sections:
      # =========================================================
      # SECTION 1: HEADER & DUAL-AUDIO COCKPIT
      # =========================================================
      - type: grid
        cards:
{chips}
{avr_vol}
{announcer}

      # =========================================================
      # SECTION 2: CINEMA, SPORTS & ARCADE EXPERIENCE
      # =========================================================
      - type: grid
        cards:
{marquee}
{eagles}
{stage}
{lighting}
{popup}
"""
    with open(target_path, "w", encoding="utf-8") as f:
        f.write(monolith)
    print(f"  ✓ Compiled monolithic master: {target_path} ({len(monolith.splitlines())} lines)")

def run_tests():
    """Runs test harness to verify output."""
    test_script = os.path.join(TESTS_DIR, "run_all_tests.py")
    print("\n▶ Running full verification test suite...")
    res = subprocess.run([sys.executable, test_script])
    return res.returncode == 0

def main():
    parser = argparse.ArgumentParser(description="Home Assistant Dashboard-as-Code Builder")
    parser.add_argument("--monolith", action="store_true", help="Compile into a single monolithic YAML file")
    parser.add_argument("--test", action="store_true", help="Run full automated verification test suite")
    args = parser.parse_args()

    print("==================================================")
    print("HOME ASSISTANT DASHBOARD-AS-CODE COMPILER")
    print("==================================================")

    if args.monolith:
        build_monolithic_basement()
    else:
        build_modular_basement()

    if args.test:
        success = run_tests()
        sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()

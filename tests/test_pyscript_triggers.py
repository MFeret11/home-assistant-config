"""
Pyscript trigger checks.

The other suites replace pyscript's decorators with fakes, so they never look at
the trigger strings themselves: a mistyped or renamed entity ID in a
@state_trigger would pass every test and then never fire. This suite loads every
pyscript file with decorators that record what they are given, then checks:
  - every file loads,
  - every @state_trigger expression is valid Python (pyscript evaluates them as Python),
  - every entity ID a @state_trigger watches is listed in docs/entities.md.

When a new trigger watches an entity that isn't in docs/entities.md, check the
entity in HA and add it there. This doesn't run the real pyscript, so it can't
catch every load error; check home-assistant.log after saving a pyscript file.

Run: python3 tests/test_pyscript_triggers.py
"""
import builtins
import glob
import importlib
import os
import re
import sys

import yaml

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PYSCRIPT_DIR = os.path.join(REPO, "pyscript")
ENTITIES_DOC = os.path.join(REPO, "docs", "entities.md")

DOMAINS = (
    "alarm_control_panel|automation|binary_sensor|button|calendar|camera|climate|counter|"
    "cover|device_tracker|event|fan|input_boolean|input_datetime|input_number|input_select|"
    "input_text|light|lock|media_player|number|person|pyscript|remote|scene|schedule|script|"
    "select|sensor|sun|switch|timer|todo|update|vacuum|weather|zone"
)
ENTITY_RE = re.compile(rf"\b(?:{DOMAINS})\.[a-z0-9_]+")

registrations = []  # (file, function, decorator, args)


def recorder(kind):
    """A stand-in for a pyscript decorator that records its arguments."""
    def decorator(*args, **kwargs):
        if kind == "service" and len(args) == 1 and callable(args[0]) and not kwargs:
            fn = args[0]
            registrations.append((fn.__module__, fn.__name__, kind, []))
            return fn

        def wrap(fn):
            registrations.append((fn.__module__, fn.__name__, kind, [str(a) for a in args]))
            return fn
        return wrap
    return decorator


class Anything:
    """Accepts any attribute access or call, so module-level code can run."""
    def __getattr__(self, name):
        return Anything()

    def __call__(self, *args, **kwargs):
        return None


class FakeState:
    def get(self, *args, **kwargs):
        return None

    def getattr(self, *args, **kwargs):
        return {}

    def set(self, *args, **kwargs):
        pass

    def persist(self, *args, **kwargs):
        pass


class FakePyscript(Anything):
    # Team Lights reads its settings (packages/sports.yaml) as pyscript.app_config.
    with open(os.path.join(REPO, "packages", "sports.yaml")) as f:
        app_config = yaml.safe_load(f)["pyscript"]["apps"]["team_lights"]


def install_fakes():
    fakes = {
        "state": FakeState(), "task": Anything(), "log": Anything(), "pyscript": FakePyscript(),
        "service": recorder("service"), "state_trigger": recorder("state_trigger"),
        "time_trigger": recorder("time_trigger"), "event_trigger": recorder("event_trigger"),
        "pyscript_compile": lambda fn: fn,
    }
    for name, value in fakes.items():
        setattr(builtins, name, value)


def documented_entities():
    text = open(ENTITIES_DOC).read()
    return set(re.findall(r"`([a-z_]+\.[a-z0-9_]+)`", text))


def main():
    install_fakes()
    for d in (PYSCRIPT_DIR, os.path.join(PYSCRIPT_DIR, "modules"), os.path.join(PYSCRIPT_DIR, "apps")):
        sys.path.insert(0, d)

    failures = []
    files = sorted(glob.glob(os.path.join(PYSCRIPT_DIR, "*.py")) + glob.glob(os.path.join(PYSCRIPT_DIR, "apps", "*.py")))
    for path in files:
        name = os.path.splitext(os.path.basename(path))[0]
        try:
            importlib.import_module(name)
        except Exception as e:
            failures.append(f"{os.path.relpath(path, REPO)} doesn't load: {type(e).__name__}: {e}")

    known = documented_entities()
    watched = set()
    triggers = 0
    for module, func, kind, args in registrations:
        if kind != "state_trigger":
            continue
        for expr in args:
            triggers += 1
            try:
                compile(expr, f"{module}.{func}", "eval")
            except SyntaxError as e:
                failures.append(f"{module}.py {func}(): trigger isn't a valid expression ({e.msg}): {expr!r}")
            for entity in ENTITY_RE.findall(expr):
                watched.add(entity)
                if entity not in known:
                    failures.append(f"{module}.py {func}(): watches {entity}, which isn't in docs/entities.md")

    if failures:
        print("FAIL: pyscript triggers")
        for f in sorted(set(failures)):
            print(f"  - {f}")
        sys.exit(1)
    print(f"PASS: {len(files)} pyscript files load; {triggers} triggers watch {len(watched)} entities, all in docs/entities.md")


if __name__ == "__main__":
    main()

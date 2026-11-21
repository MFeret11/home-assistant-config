"""
Shared entity ID checks.

pyscript/modules/shared_entities.py holds the entity IDs that theater.py and
basement.py share. interlocks.py keeps its own copies so that saving the shared
module can't reload it and kill a running projector cooldown. This suite fails
when:
  - a constant in interlocks.py has a different value from the shared module,
  - any pyscript file defines a shared name with a different value, or
  - theater.py or basement.py defines a shared name itself instead of importing it.

Run: python3 tests/test_shared_entities.py
"""
import ast
import glob
import os
import sys

PYSCRIPT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "pyscript"))
SHARED_PATH = os.path.join(PYSCRIPT_DIR, "modules", "shared_entities.py")
IMPORTERS = {"theater.py", "basement.py"}


def string_constants(path):
    """Top-level NAME = "literal" assignments in a file."""
    tree = ast.parse(open(path).read(), path)
    found = {}
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id.isupper()
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)):
            found[node.targets[0].id] = node.value.value
    return found


def imported_names(path):
    tree = ast.parse(open(path).read(), path)
    names = set()
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "shared_entities":
            names.update(a.name for a in node.names)
    return names


def main():
    shared = string_constants(SHARED_PATH)
    failures = []
    if not shared:
        failures.append("shared_entities.py defines no constants")

    files = sorted(glob.glob(os.path.join(PYSCRIPT_DIR, "*.py"))
                   + glob.glob(os.path.join(PYSCRIPT_DIR, "apps", "*.py")))
    for path in files:
        rel = os.path.relpath(path, PYSCRIPT_DIR)
        local = string_constants(path)
        for name, value in local.items():
            if name in shared and value != shared[name]:
                failures.append(f"{rel}: {name} = {value!r}, shared module has {shared[name]!r}")
            elif name in shared and rel in IMPORTERS:
                failures.append(f"{rel}: defines {name} itself; import it from shared_entities")
        if rel in IMPORTERS:
            missing = imported_names(path) - set(shared)
            for name in sorted(missing):
                failures.append(f"{rel}: imports {name}, which shared_entities.py doesn't define")

    # interlocks.py must not import the shared module (a save would reload it).
    if imported_names(os.path.join(PYSCRIPT_DIR, "interlocks.py")):
        failures.append("interlocks.py imports shared_entities; keep local copies instead")

    if failures:
        print("FAIL: shared entity IDs")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print(f"PASS: {len(shared)} shared IDs, interlocks.py copies match, no shadowing")


if __name__ == "__main__":
    main()

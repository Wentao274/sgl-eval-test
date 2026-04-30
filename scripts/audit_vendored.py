"""Static check: no untranslated `from nemo_skills.X` imports under
``sgl_eval/_vendored/``. Run by tests/test_no_untranslated_imports.py and
manually as a CI invariant.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parent.parent
VENDOR_ROOT = ROOT / "sgl_eval" / "_vendored"

PATTERN = re.compile(r"^\s*(?:from|import)\s+nemo_skills(?:\.|\s|$)", re.MULTILINE)


def find_untranslated() -> List[tuple[Path, list[str]]]:
    bad: list[tuple[Path, list[str]]] = []
    if not VENDOR_ROOT.exists():
        return bad
    for py in VENDOR_ROOT.rglob("*.py"):
        text = py.read_text()
        hits = PATTERN.findall(text)
        if hits:
            bad.append((py, hits))
    return bad


def main() -> int:
    bad = find_untranslated()
    if bad:
        print("Untranslated nemo_skills imports found:")
        for path, hits in bad:
            print(f"  {path.relative_to(ROOT)}: {len(hits)} occurrence(s)")
        return 1
    print("OK: all _vendored imports translated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

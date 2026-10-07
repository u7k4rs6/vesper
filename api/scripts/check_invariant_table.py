"""Fail if the invariant test table in docs/04_SECURITY.md §6 changed, or if any test it names is missing.

The table is the contract with reviewers (04_SECURITY.md §6). Renaming or deleting one of its tests, or
editing the table, must be a deliberate act: update the checksum below in the same commit.
"""

import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_SHA256 = "b0c6ab3d122e97e2e68882b9fd68e58e0b96b0a76aaf1a842df99ee18791d74e"


def table_rows() -> list[str]:
    text = (ROOT / "docs" / "04_SECURITY.md").read_text(encoding="utf-8")
    section = text.split("## 6.", 1)[1].split("\n## ", 1)[0]
    return [line.strip() for line in section.splitlines() if line.strip().startswith("| `test_")]


def main() -> int:
    rows = table_rows()
    digest = hashlib.sha256("\n".join(rows).encode()).hexdigest()
    names = [re.search(r"`(test_\w+)`", r).group(1) for r in rows]
    sources = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "api" / "tests").glob("test_*.py"))
    missing = [n for n in names if not re.search(rf"^def {n}\(", sources, re.M)]
    problems = []
    if digest != EXPECTED_SHA256:
        problems.append(f"the table changed (sha256 {digest}); update EXPECTED_SHA256 deliberately")
    if missing:
        problems.append(f"tests named in the table do not exist: {', '.join(missing)}")
    if problems:
        print("\n".join(f"FAIL  {p}" for p in problems), file=sys.stderr)
        return 1
    print(f"ok    {len(names)} invariant tests present, table unchanged")
    return 0


if __name__ == "__main__":
    sys.exit(main())

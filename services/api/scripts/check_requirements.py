"""Fail if requirements.txt and pyproject.toml list different runtime dependencies."""

import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _name(requirement: str) -> str:
    return re.split(r"[\[<>=!~ ;]", requirement.strip(), maxsplit=1)[0].lower().replace("_", "-")


def main() -> int:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    expected = {_name(r) for r in project["dependencies"]}
    expected |= {_name(r) for r in project["optional-dependencies"].get("postgres", [])}
    lines = (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
    listed = {_name(line) for line in lines if line.strip() and not line.startswith("#")}
    missing, extra = expected - listed, listed - expected
    if missing or extra:
        print(f"requirements.txt is out of sync. Missing: {sorted(missing)} Extra: {sorted(extra)}")
        return 1
    print("requirements.txt matches pyproject.toml")
    return 0


if __name__ == "__main__":
    sys.exit(main())

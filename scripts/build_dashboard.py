#!/usr/bin/env python3
from __future__ import annotations

import json
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "site" / "data.json"


def build_profile(manifest_path: Path) -> dict:
    manifest = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    repository_rows = manifest.get("repositories", [])
    repositories = []
    for row in repository_rows:
        repositories.append(
            {
                "id": row["id"],
                "github": row.get("github"),
                "architecture": row["architecture"],
                "modules": row.get("modules", []),
                "tags": row.get("tags", []),
                "ci": row.get("ci", True),
            }
        )

    changes = []
    for path in sorted((manifest_path.parent / "changes").glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not raw.get("enabled", False):
            continue
        changes.append(
            {
                "id": raw["id"],
                "title": raw["title"],
                "description": raw.get("description", ""),
                "source": raw.get("source", {}),
                "trigger": raw.get("trigger"),
                "scope": raw.get("scope"),
                "tracking": raw["tracking"],
                "metrics": raw.get("metrics", {}),
                "automated": bool(raw.get("steps")),
            }
        )

    return {
        "id": manifest_path.parent.name,
        "owner": manifest["fleet"]["owner"],
        "repositories": repositories,
        "changes": changes,
    }


def main() -> None:
    profiles = [
        build_profile(path)
        for path in sorted((ROOT / "users").glob("*/fleet.toml"))
    ]
    payload = {"schema": 1, "profiles": profiles}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUTPUT.relative_to(ROOT)} ({len(profiles)} profile(s))")


if __name__ == "__main__":
    main()

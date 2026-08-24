#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "site" / "data.json"
sys.path.insert(0, str(ROOT / "src"))

from zmk_shield_fleet.core import load_manifest  # noqa: E402


def build_profile(manifest_path: Path) -> dict:
    manifest = load_manifest(manifest_path)
    repositories = []
    for row in manifest.repositories.values():
        repositories.append(
            {
                "id": row.id,
                "github": row.github,
                "architecture": row.architecture,
                "rollout_order": row.rollout_order,
                "modules": list(row.modules),
                "tags": list(row.tags),
                "ci": row.ci,
            }
        )

    next_actions = [
        {
            "id": action.id,
            "state": action.state,
            "priority": action.priority,
            "order": action.order,
            "repository": action.repository,
            "action": action.action,
            "completion": action.completion,
            "blocker": action.blocker,
            "pr": action.pr,
            "repository_url": action.repository_url,
        }
        for action in manifest.next_actions
    ]

    changes = []
    for path in sorted((manifest_path.parent / "changes").glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not raw.get("enabled", False):
            continue
        changes.append(
            {
                "id": raw["id"],
                "dashboard_label": raw.get("dashboard_label"),
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
        "owner": manifest.owner,
        "repositories": repositories,
        "next_actions": next_actions,
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

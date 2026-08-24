#!/usr/bin/env python3
from __future__ import annotations

import json
import html as html_lib
import os
import re
import subprocess
import sys
from dataclasses import fields, is_dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "site" / "data.json"
INDEX = ROOT / "site" / "index.html"
sys.path.insert(0, str(ROOT / "src"))

from zmk_shield_fleet.core import load_ledger_entry, load_manifest  # noqa: E402


def _jsonable(value: Any) -> Any:
    """Convert an already-validated model value into JSON-safe primitives."""
    if is_dataclass(value):
        return {field.name: _jsonable(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list, set, frozenset)):
        return [_jsonable(item) for item in value]
    if isinstance(value, Path):
        return value.as_posix()
    return value


def _optional_attr(value: Any, name: str, default: Any = None) -> Any:
    return _jsonable(getattr(value, name, default))


def _git(*args: str) -> str | None:
    command = ["git", "-C", str(ROOT), *args]
    git_marker = ROOT / ".git"
    if git_marker.is_file():
        marker = git_marker.read_text(encoding="utf-8").strip()
        if marker.startswith("gitdir: "):
            git_dir = marker.removeprefix("gitdir: ")
            wsl_match = re.match(r"//wsl\.localhost/[^/]+(/.*)", git_dir)
            if wsl_match:
                git_dir = wsl_match.group(1)
            command = ["git", f"--git-dir={git_dir}", f"--work-tree={ROOT}", *args]
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


def _github_project_url() -> str:
    configured = os.environ.get("FLEET_PROJECT_URL")
    if configured:
        return configured.rstrip("/")
    github_repository = os.environ.get("GITHUB_REPOSITORY")
    if github_repository:
        return f"https://github.com/{github_repository}"
    remote = _git("config", "--get", "remote.origin.url") or ""
    ssh_match = re.fullmatch(r"git@github\.com:([^/]+/[^/]+?)(?:\.git)?", remote)
    https_match = re.fullmatch(r"https://github\.com/([^/]+/[^/]+?)(?:\.git)?/?", remote)
    match = ssh_match or https_match
    return f"https://github.com/{match.group(1)}" if match else ""


def _site_url(project_url: str) -> str:
    configured = os.environ.get("FLEET_SITE_URL")
    if configured:
        return configured.rstrip("/") + "/"
    match = re.fullmatch(r"https://github\.com/([^/]+)/([^/]+)", project_url)
    if not match:
        return ""
    owner, repository = match.groups()
    return f"https://{owner}.github.io/{repository}/"


def _scope_payload(entry: Any) -> dict[str, Any]:
    if entry.scope_all:
        return {"kind": "all", "repositories": list(entry.campaign.repositories)}
    if entry.scope_module:
        return {
            "kind": "module",
            "module": entry.scope_module,
            "repositories": list(entry.campaign.repositories),
        }
    repositories = list(entry.campaign.repositories)
    return {
        "kind": "single" if len(repositories) == 1 else "explicit",
        "repositories": repositories,
    }


def _source_payload(source: Any) -> dict[str, Any]:
    return {
        "repository": source.repository,
        "from_revision": source.from_revision,
        "to_revision": source.to_revision,
        "change_url": source.change_url,
        "notes": source.notes,
    }


def _trigger_payload(trigger: Any) -> dict[str, Any] | None:
    if trigger is None:
        return None
    return {
        "repository": trigger.repository,
        "revision": trigger.revision,
        "change_url": trigger.change_url,
        "notes": trigger.notes,
    }


def _target_payload(target: Any) -> dict[str, Any]:
    return {
        "status": target.status,
        "pr": target.pr,
        "commit": target.commit,
        "notes": target.notes,
        "validation": dict(target.validation),
        "validation_urls": dict(target.validation_urls),
        "branch": _optional_attr(target, "branch"),
        "base_branch": _optional_attr(target, "base_branch"),
        "pr_head": _optional_attr(target, "pr_head"),
        "variants": _optional_attr(target, "variants", []),
        "findings": _optional_attr(target, "findings", 0),
    }


def _action_payload(action: Any) -> dict[str, Any]:
    return {
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
        "change_id": _optional_attr(action, "change_id"),
        "validation_keys": _optional_attr(action, "validation_keys", []),
        "variant_ids": _optional_attr(action, "variant_ids", []),
        "evidence": _optional_attr(action, "evidence", []),
    }


def _profile_locale(manifest: Any) -> str:
    configured = _optional_attr(manifest, "locale")
    if configured:
        return configured
    sample = " ".join(
        f"{action.action} {action.completion} {action.blocker}"
        for action in manifest.next_actions
    )
    return "ja" if re.search(r"[\u3040-\u30ff\u3400-\u9fff]", sample) else "en"


def _write_static_metadata(project_name: str, site_url: str) -> None:
    """Keep crawler-visible metadata configurable for forks and Pages builds."""
    html = INDEX.read_text(encoding="utf-8")
    values = {
        'property="og:title"': html_lib.escape(project_name, quote=True),
        'name="twitter:title"': html_lib.escape(project_name, quote=True),
        'property="og:url"': html_lib.escape(site_url, quote=True),
        'property="og:image"': html_lib.escape(f"{site_url}og.png" if site_url else "og.png", quote=True),
        'name="twitter:image"': html_lib.escape(f"{site_url}og.png" if site_url else "og.png", quote=True),
    }
    for selector, value in values.items():
        pattern = rf'(<meta {re.escape(selector)} content=")[^"]*(">)'
        html, replacements = re.subn(pattern, lambda match: f"{match.group(1)}{value}{match.group(2)}", html, count=1)
        if replacements != 1:
            raise RuntimeError(f"missing dashboard metadata tag: {selector}")
    escaped_name = html_lib.escape(project_name)
    html, replacements = re.subn(
        r"(<title>)[^<]*(</title>)",
        lambda match: f"{match.group(1)}{escaped_name}{match.group(2)}",
        html,
        count=1,
    )
    if replacements != 1:
        raise RuntimeError("missing dashboard title")
    INDEX.write_text(html, encoding="utf-8")


def build_profile(manifest_path: Path) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    repositories = [
        {
            "id": row.id,
            "github": row.github,
            "architecture": row.architecture,
            "rollout_order": row.rollout_order,
            "modules": list(row.modules),
            "tags": list(row.tags),
            "ci": row.ci,
            "default_branch": row.default_branch,
            "maintenance_branch": row.maintenance_branch,
            "rollout_enabled": _optional_attr(row, "rollout_enabled", True),
        }
        for row in manifest.repositories.values()
    ]

    changes = []
    for path in sorted((manifest_path.parent / "changes").glob("*.json")):
        entry = load_ledger_entry(manifest, path)
        if not entry.campaign.enabled:
            continue
        changes.append(
            {
                "id": entry.campaign.id,
                "dashboard_label": _optional_attr(entry.campaign, "dashboard_label"),
                "title": entry.campaign.title,
                "description": entry.campaign.description,
                "source": _source_payload(entry.source),
                "trigger": _trigger_payload(entry.trigger),
                "scope": _scope_payload(entry),
                "tracking": {
                    repository: _target_payload(target)
                    for repository, target in entry.tracking.items()
                },
                "metrics": _optional_attr(entry, "metrics", {}),
                "automated": bool(entry.campaign.steps),
            }
        )

    return {
        "id": manifest_path.parent.name,
        "owner": manifest.owner,
        "locale": _profile_locale(manifest),
        "repositories": repositories,
        "next_actions": [_action_payload(action) for action in manifest.next_actions],
        "changes": changes,
    }


def main() -> None:
    project_url = _github_project_url()
    project_name = os.environ.get("FLEET_PROJECT_NAME", "ZMK Shield Fleet")
    site_url = _site_url(project_url)
    profiles = [
        build_profile(path)
        for path in sorted((ROOT / "users").glob("*/fleet.toml"))
    ]
    payload = {
        "schema": 2,
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "source_commit": os.environ.get("FLEET_SOURCE_COMMIT")
        or os.environ.get("GITHUB_SHA")
        or _git("rev-parse", "HEAD"),
        "project": {
            "name": project_name,
            "url": project_url,
            "site_url": site_url,
        },
        "locale": os.environ.get("FLEET_LOCALE", "en"),
        "profiles": profiles,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    _write_static_metadata(project_name, site_url)
    print(f"wrote {OUTPUT.relative_to(ROOT)} ({len(profiles)} profile(s))")


if __name__ == "__main__":
    main()

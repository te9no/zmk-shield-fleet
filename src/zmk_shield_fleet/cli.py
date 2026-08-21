from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from .core import (
    FleetError,
    apply_campaign,
    audit_fleet,
    campaign_diff,
    campaign_matrix,
    clone_repositories,
    inventory_rows,
    json_compact,
    load_campaign,
    load_manifest,
    plan_campaign,
    resolve_workspace,
    select_repositories,
)


def _common_parser(*, selectors: bool = True) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--manifest",
        default="fleet.toml",
        help="fleet manifest path (default: ./fleet.toml)",
    )
    parser.add_argument(
        "--workspace",
        help="directory containing managed repository checkouts",
    )
    if selectors:
        parser.add_argument(
            "--repo",
            action="append",
            dest="repositories",
            metavar="ID",
            help="limit the operation to a repository id; repeatable",
        )
        parser.add_argument(
            "--tag",
            action="append",
            dest="tags",
            metavar="TAG",
            help="require a repository tag; repeatable",
        )
        parser.add_argument(
            "--ci-only",
            action="store_true",
            help="exclude local-only repositories",
        )
    return parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="shield-fleet",
        description="Guarded cross-repository maintenance for modular ZMK shields.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    common = _common_parser()

    inventory = subparsers.add_parser(
        "inventory", parents=[common], help="show managed repositories and checkout state"
    )
    inventory.add_argument("--json", action="store_true", help="emit JSON")

    audit = subparsers.add_parser(
        "audit", parents=[common], help="validate checkouts, contracts, and mirror drift"
    )
    audit.add_argument("--strict", action="store_true", help="treat warnings as failures")
    audit.add_argument("--json", action="store_true", help="emit JSON")

    clone = subparsers.add_parser(
        "clone", parents=[common], help="clone missing managed repositories"
    )
    clone.add_argument(
        "--depth",
        type=int,
        default=1,
        help="shallow clone depth; use 0 for full history (default: 1)",
    )

    campaign = subparsers.add_parser("campaign", help="plan or apply a guarded migration")
    campaign_subparsers = campaign.add_subparsers(dest="campaign_command", required=True)
    campaign_common = _common_parser()

    targets = campaign_subparsers.add_parser(
        "targets", parents=[campaign_common], help="emit a campaign target list"
    )
    targets.add_argument("campaign", help="campaign id or JSON path")
    targets.add_argument(
        "--github-matrix",
        action="store_true",
        help="emit a compact GitHub Actions matrix",
    )

    plan = campaign_subparsers.add_parser(
        "plan", parents=[campaign_common], help="preflight a campaign without writing"
    )
    plan.add_argument("campaign", help="campaign id or JSON path")
    plan.add_argument("--diff", action="store_true", help="show the unified diff")

    apply = campaign_subparsers.add_parser(
        "apply", parents=[campaign_common], help="preflight and apply a campaign"
    )
    apply.add_argument("campaign", help="campaign id or JSON path")
    apply.add_argument("--diff", action="store_true", help="show the unified diff before writing")
    apply.add_argument(
        "--allow-dirty",
        action="store_true",
        help="allow writes to repositories with existing changes",
    )
    return parser


def _load_context(args: argparse.Namespace):
    manifest = load_manifest(args.manifest)
    workspace = resolve_workspace(manifest, args.workspace)
    return manifest, workspace


def _print_table(rows: Sequence[dict[str, Any]]) -> None:
    if not rows:
        print("No repositories selected.")
        return
    headers = ("ID", "ARCHITECTURE", "MODULES", "BRANCH", "STATE", "CI")
    rendered = [
        (
            str(row["id"]),
            str(row["architecture"]),
            ",".join(row["modules"]),
            str(row["branch"]),
            str(row["state"]),
            "yes" if row["ci"] else "no",
        )
        for row in rows
    ]
    widths = [
        max(len(headers[index]), *(len(row[index]) for row in rendered))
        for index in range(len(headers))
    ]
    print("  ".join(value.ljust(widths[index]) for index, value in enumerate(headers)))
    print("  ".join("-" * width for width in widths))
    for row in rendered:
        print("  ".join(value.ljust(widths[index]) for index, value in enumerate(row)))


def _selected(args: argparse.Namespace, manifest):
    return select_repositories(
        manifest,
        getattr(args, "repositories", None),
        getattr(args, "tags", None),
        ci_only=getattr(args, "ci_only", False),
    )


def _campaign_repository_filter(
    args: argparse.Namespace, campaign
) -> tuple[list[str], list[str], bool]:
    repositories = getattr(args, "repositories", None)
    if repositories is None:
        selected = list(campaign.repositories)
    else:
        selected = list(repositories)
    tags = getattr(args, "tags", None) or []
    ci_only = getattr(args, "ci_only", False)
    return tuple(selected), tags, ci_only


def _print_campaign_plan(plan) -> None:
    print(f"Campaign: {plan.campaign.id} — {plan.campaign.title}")
    for result in plan.results:
        state = "up-to-date" if result.pending == 0 else f"{result.pending} pending"
        if result.already:
            state += f", {result.already} already"
        print(
            f"  {result.repository}/{result.step}: {state}; "
            f"{result.files} file(s); expected {result.expected.describe()}"
        )
    repositories = sorted({change.repository for change in plan.changes})
    print(
        f"Changes: {len(plan.changes)} file(s) in {len(repositories)} repository/repositories"
    )


def _resolve_campaign_selection(args: argparse.Namespace, manifest, campaign):
    selected_ids, tags, ci_only = _campaign_repository_filter(args, campaign)
    selected_specs = select_repositories(
        manifest, selected_ids, tags, ci_only=ci_only
    )
    filtered_ids = tuple(repo.id for repo in selected_specs if repo.id in campaign.repositories)
    outside = set(selected_ids).difference(campaign.repositories)
    if outside:
        raise FleetError(
            f"repository filter is outside this campaign: {', '.join(sorted(outside))}"
        )
    if not filtered_ids:
        raise FleetError("campaign filters selected no repositories")
    return filtered_ids


def dispatch(args: argparse.Namespace) -> int:
    if args.command == "inventory":
        manifest, workspace = _load_context(args)
        rows = inventory_rows(manifest, workspace, _selected(args, manifest))
        if args.json:
            print(json.dumps(rows, ensure_ascii=False, indent=2))
        else:
            _print_table(rows)
            print(f"\nWorkspace: {workspace}")
        return 0

    if args.command == "audit":
        manifest, workspace = _load_context(args)
        repositories = _selected(args, manifest)
        issues = audit_fleet(manifest, workspace, repositories)
        if args.json:
            payload = [issue.__dict__ for issue in issues]
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        elif not issues:
            print(f"OK: audited {len(repositories)} repositories in {workspace}")
        else:
            for issue in issues:
                print(f"{issue.level.upper():7} {issue.subject}: {issue.message}")
            error_count = sum(issue.level == "error" for issue in issues)
            warning_count = sum(issue.level == "warning" for issue in issues)
            print(f"\nAudit: {error_count} error(s), {warning_count} warning(s)")
        has_errors = any(issue.level == "error" for issue in issues)
        has_warnings = any(issue.level == "warning" for issue in issues)
        return 1 if has_errors or (args.strict and has_warnings) else 0

    if args.command == "clone":
        manifest, workspace = _load_context(args)
        depth = None if args.depth == 0 else args.depth
        if depth is not None and depth < 1:
            raise FleetError("--depth must be 0 or a positive integer")
        messages = clone_repositories(
            manifest, workspace, _selected(args, manifest), depth=depth
        )
        for message in messages:
            print(message)
        return 0

    if args.command == "campaign":
        manifest, workspace = _load_context(args)
        loaded = load_campaign(manifest, args.campaign)
        selected_ids = _resolve_campaign_selection(args, manifest, loaded)

        if args.campaign_command == "targets":
            matrix = campaign_matrix(
                manifest,
                loaded,
                selected_ids,
                ci_only=getattr(args, "ci_only", False),
            )
            if args.github_matrix:
                print(json_compact(matrix))
            else:
                for item in matrix["include"]:
                    print(
                        f"{item['id']}\t{item['github']}\t"
                        f"{item['maintenance_branch']}\t{item['checkout']}"
                    )
            return 0

        planned = plan_campaign(manifest, workspace, loaded, selected_ids)
        _print_campaign_plan(planned)
        if args.diff and planned.changes:
            print()
            print(campaign_diff(planned), end="")
        if args.campaign_command == "apply":
            apply_campaign(
                manifest,
                workspace,
                planned,
                allow_dirty=args.allow_dirty,
            )
            if planned.changes:
                print(f"Applied {len(planned.changes)} file change(s).")
            else:
                print("Nothing to apply; all selected repositories are up to date.")
        return 0

    raise FleetError(f"unsupported command: {args.command}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return dispatch(args)
    except FleetError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("error: interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())

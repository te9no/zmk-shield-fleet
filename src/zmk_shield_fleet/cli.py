from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from .core import (
    LEDGER_STATUSES,
    FleetError,
    apply_campaign,
    audit_fleet,
    campaign_diff,
    campaign_matrix,
    clone_repositories,
    inventory_rows,
    json_compact,
    list_ledger_entries,
    load_campaign,
    load_ledger_entry,
    load_manifest,
    mark_ledger_target,
    plan_campaign,
    revision_findings,
    resolve_workspace,
    select_repositories,
    sync_ledger_entry,
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
        description="Track and propagate shared ZMK driver changes across keyboard repositories.",
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

    revisions = subparsers.add_parser(
        "revisions", parents=[common], help="find moving or non-SHA west revisions"
    )
    revisions.add_argument(
        "--strict-sha", action="store_true", help="report tags and every non-40-character SHA"
    )
    revisions.add_argument("--check", action="store_true", help="fail when findings exist")
    revisions.add_argument("--json", action="store_true", help="emit JSON")

    clone = subparsers.add_parser(
        "clone", parents=[common], help="clone missing managed repositories"
    )
    clone.add_argument(
        "--depth",
        type=int,
        default=1,
        help="shallow clone depth; use 0 for full history (default: 1)",
    )

    for command, help_text in (
        ("change", "plan or apply the file changes recorded in a ledger entry"),
        ("campaign", "backward-compatible alias for change"),
    ):
        change = subparsers.add_parser(command, help=help_text)
        change_subparsers = change.add_subparsers(dest="change_command", required=True)
        change_common = _common_parser()

        targets = change_subparsers.add_parser(
            "targets", parents=[change_common], help="emit a change target list"
        )
        targets.add_argument("change", help="change id or JSON path")
        targets.add_argument(
            "--github-matrix", action="store_true", help="emit a compact GitHub Actions matrix"
        )

        plan = change_subparsers.add_parser(
            "plan", parents=[change_common], help="preflight a change without writing"
        )
        plan.add_argument("change", help="change id or JSON path")
        plan.add_argument("--diff", action="store_true", help="show the unified diff")

        apply = change_subparsers.add_parser(
            "apply", parents=[change_common], help="preflight and apply a change"
        )
        apply.add_argument("change", help="change id or JSON path")
        apply.add_argument("--diff", action="store_true", help="show the unified diff before writing")
        apply.add_argument(
            "--allow-dirty", action="store_true",
            help="allow writes to repositories with existing changes",
        )

    ledger = subparsers.add_parser("ledger", help="inspect and update the driver-change ledger")
    ledger_subparsers = ledger.add_subparsers(dest="ledger_command", required=True)
    ledger_common = _common_parser(selectors=False)
    ledger_subparsers.add_parser("list", parents=[ledger_common], help="list all changes")
    show = ledger_subparsers.add_parser("show", parents=[ledger_common], help="show one change")
    show.add_argument("change", help="change id or JSON path")
    check = ledger_subparsers.add_parser("check", parents=[ledger_common], help="validate entries")
    check.add_argument("change", nargs="?", help="optional change id or JSON path")
    sync = ledger_subparsers.add_parser("sync", parents=[ledger_common], help="sync PR states")
    sync.add_argument("change", nargs="?", help="optional change id or JSON path")
    sync.add_argument("--write", action="store_true", help="write discovered states to JSON")
    mark = ledger_subparsers.add_parser("mark", parents=[ledger_common], help="update one target")
    mark.add_argument("change", help="change id or JSON path")
    mark.add_argument("--repo", required=True, help="repository id")
    mark.add_argument("--status", required=True, choices=sorted(LEDGER_STATUSES))
    mark.add_argument("--pr", help="pull request URL; pass an empty value to clear")
    mark.add_argument("--commit", help="applied/merge commit; pass an empty value to clear")
    mark.add_argument("--notes", help="free-form note")
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
    print(f"Change: {plan.campaign.id} — {plan.campaign.title}")
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
    if args.command == "ledger":
        manifest = load_manifest(args.manifest)
        if args.ledger_command in {"list", "check", "sync"} and not getattr(args, "change", None):
            entries = list_ledger_entries(manifest)
        else:
            entries = (load_ledger_entry(manifest, args.change),)

        if args.ledger_command == "list":
            if not entries:
                print("No ledger entries.")
            for entry in entries:
                counts: dict[str, int] = {}
                for target in entry.tracking.values():
                    counts[target.status] = counts.get(target.status, 0) + 1
                summary = ", ".join(f"{key}={counts[key]}" for key in sorted(counts))
                print(f"{entry.campaign.id}\t{entry.source.to_revision}\t{summary}")
            return 0

        if args.ledger_command == "check":
            print(f"OK: validated {len(entries)} ledger entry/entries")
            return 0

        if args.ledger_command == "show":
            entry = entries[0]
            print(f"{entry.campaign.id}: {entry.campaign.title}")
            print(f"Source: {entry.source.repository} -> {entry.source.to_revision}")
            if entry.trigger:
                print(f"Trigger: {entry.trigger.repository}@{entry.trigger.revision}")
            if entry.scope_module:
                print(f"Scope: every repository with module={entry.scope_module}")
            elif entry.scope_all:
                print("Scope: every managed repository")
            for repo_id, target in entry.tracking.items():
                details = target.pr or target.commit or "-"
                print(f"  {repo_id}: {target.status} ({details})")
            return 0

        if args.ledger_command == "mark":
            mark_ledger_target(
                entries[0], args.repo, args.status, pr=args.pr,
                commit=args.commit, notes=args.notes,
            )
            print(f"Updated {entries[0].campaign.id}/{args.repo}: {args.status}")
            return 0

        if args.ledger_command == "sync":
            for entry in entries:
                tracking = sync_ledger_entry(manifest, entry, write=args.write)
                for repo_id, target in tracking.items():
                    print(f"{entry.campaign.id}\t{repo_id}\t{target.status}\t{target.pr or '-'}")
            return 0

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

    if args.command == "revisions":
        manifest, workspace = _load_context(args)
        findings = revision_findings(
            workspace, _selected(args, manifest), strict_sha=args.strict_sha
        )
        if args.json:
            print(json.dumps([finding.__dict__ for finding in findings], ensure_ascii=False, indent=2))
        elif not findings:
            print("OK: no matching revision findings")
        else:
            for finding in findings:
                print(
                    f"{finding.kind:10} {finding.repository}:"
                    f"{finding.path}:{finding.line} {finding.revision}"
                )
            print(f"\nRevision audit: {len(findings)} finding(s)")
        return 1 if args.check and findings else 0

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

    if args.command in {"change", "campaign"}:
        manifest, workspace = _load_context(args)
        loaded = load_campaign(manifest, args.change)
        selected_ids = _resolve_campaign_selection(args, manifest, loaded)

        if args.change_command == "targets":
            if not loaded.steps:
                raise FleetError(
                    f"change {loaded.id!r} is ledger-only and has no automated steps"
                )
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
        if args.change_command == "apply":
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

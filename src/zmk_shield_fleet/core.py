from __future__ import annotations

import difflib
import fnmatch
import hashlib
import json
import os
import re
import shlex
import stat
import subprocess
import tempfile
import tomllib
import urllib.parse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
GITHUB_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
MAX_TEXT_FILE_SIZE = 2 * 1024 * 1024
NEXT_ACTION_STATES = frozenset({"active", "waiting", "later"})
NEXT_ACTION_PRIORITIES = frozenset({"high", "medium", "low"})
EVIDENCE_STATUSES = frozenset({"passed", "pending", "failed", "waived", "info"})


class FleetError(RuntimeError):
    """A user-correctable fleet configuration or operation error."""


@dataclass(frozen=True)
class RepositorySpec:
    id: str
    checkout: str
    default_branch: str
    maintenance_branch: str
    architecture: str
    modules: tuple[str, ...]
    tags: tuple[str, ...]
    required_globs: tuple[str, ...]
    rollout_order: int | None = None
    github: str | None = None
    ci: bool = True
    rollout_enabled: bool = False
    allow_external: bool = False

    @property
    def clone_url(self) -> str | None:
        if self.github is None:
            return None
        return f"https://github.com/{self.github}.git"


@dataclass(frozen=True)
class MirrorMember:
    repository: str
    path: str
    include: tuple[str, ...]
    exclude: tuple[str, ...]


@dataclass(frozen=True)
class MirrorSpec:
    id: str
    description: str
    enforce: bool
    members: tuple[MirrorMember, ...]


@dataclass(frozen=True)
class NextActionSpec:
    id: str
    state: str
    priority: str
    order: int
    repository: str
    action: str
    completion: str
    blocker: str
    pr: str | None = None
    repository_url: str | None = None
    change_id: str | None = None
    validation_keys: tuple[str, ...] = ()
    variant_ids: tuple[str, ...] = ()
    evidence: tuple[EvidenceSpec, ...] = ()


@dataclass(frozen=True)
class EvidenceSpec:
    label: str
    status: str
    url: str


@dataclass(frozen=True)
class Manifest:
    path: Path
    owner: str
    default_workspace: Path
    repositories: Mapping[str, RepositorySpec]
    mirrors: tuple[MirrorSpec, ...]
    next_actions: tuple[NextActionSpec, ...]


@dataclass(frozen=True)
class Expectation:
    minimum: int
    maximum: int

    def accepts(self, value: int) -> bool:
        return self.minimum <= value <= self.maximum

    def describe(self) -> str:
        if self.minimum == self.maximum:
            return str(self.minimum)
        return f"{self.minimum}..{self.maximum}"


@dataclass(frozen=True)
class CampaignStep:
    id: str
    repositories: tuple[str, ...]
    paths: tuple[str, ...]
    operation: str
    find: str
    replace: str
    expect: Mapping[str, Expectation]
    flags: tuple[str, ...] = ()
    already_pattern: str | None = None


@dataclass(frozen=True)
class Campaign:
    path: Path
    id: str
    title: str
    description: str
    enabled: bool
    repositories: tuple[str, ...]
    steps: tuple[CampaignStep, ...]


LEDGER_STATUSES = frozenset(
    {"pending", "pr-open", "merged", "applied", "closed", "blocked", "not-applicable"}
)
VALIDATION_STATUSES = frozenset({"pending", "passed", "failed", "waived"})


@dataclass(frozen=True)
class ChangeSource:
    repository: str
    from_revision: str | None
    to_revision: str
    change_url: str | None
    notes: str


@dataclass(frozen=True)
class ChangeTrigger:
    repository: str
    revision: str
    change_url: str
    notes: str


@dataclass(frozen=True)
class TargetTracking:
    status: str
    pr: str | None
    commit: str | None
    notes: str
    validation: Mapping[str, str]
    validation_urls: Mapping[str, str]
    branch: str | None = None
    base_branch: str | None = None
    pr_head: str | None = None
    required_validation: tuple[str, ...] = ()
    variants: tuple[ValidationVariant, ...] = ()
    findings: int | None = None


@dataclass(frozen=True)
class ValidationVariant:
    id: str
    status: str
    validation: Mapping[str, str]
    evidence: tuple[EvidenceSpec, ...]


@dataclass(frozen=True)
class LocalRevisionBaseline:
    repository: str
    findings: int
    status: str


@dataclass(frozen=True)
class RevisionMetrics:
    finding_total: int | None = None
    measured_at: str | None = None
    measurement_mode: str | None = None
    measurement_command: str | None = None
    fleet_commit: str | None = None
    audit_run: str | None = None
    measurement_scope: str | None = None
    evidence_status: str | None = None
    local_only_baseline: LocalRevisionBaseline | None = None


@dataclass(frozen=True)
class LedgerEntry:
    campaign: Campaign
    source: ChangeSource
    trigger: ChangeTrigger | None
    scope_module: str | None
    scope_all: bool
    tracking: Mapping[str, TargetTracking]
    metrics: RevisionMetrics | None = None

    @property
    def path(self) -> Path:
        return self.campaign.path


@dataclass(frozen=True)
class AuditIssue:
    level: str
    subject: str
    message: str


@dataclass(frozen=True)
class RevisionFinding:
    repository: str
    path: str
    line: int
    revision: str
    kind: str


@dataclass(frozen=True)
class StepResult:
    step: str
    repository: str
    files: int
    pending: int
    already: int
    expected: Expectation


@dataclass
class FileChange:
    repository: str
    path: Path
    relative_path: str
    before: str
    after: str
    steps: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CampaignPlan:
    campaign: Campaign
    selected_repositories: tuple[str, ...]
    results: tuple[StepResult, ...]
    changes: tuple[FileChange, ...]
    checkout_heads: Mapping[str, str] = field(default_factory=dict)


def _require_mapping(value: Any, context: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise FleetError(f"{context} must be an object/table")
    return value


def _reject_unknown_keys(
    value: Mapping[str, Any], allowed: set[str] | frozenset[str], context: str
) -> None:
    unknown = sorted(set(value).difference(allowed))
    if unknown:
        raise FleetError(f"{context} contains unknown key(s): {', '.join(unknown)}")


def _require_string(value: Any, context: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value):
        raise FleetError(f"{context} must be a non-empty string")
    return value


def _optional_string(value: Any, context: str) -> str | None:
    if value is None:
        return None
    return _require_string(value, context)


def _optional_http_url(value: Any, context: str) -> str | None:
    url = _optional_string(value, context)
    if url is not None:
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            raise FleetError(f"{context} must be a public HTTPS URL")
    return url


def _require_https_url(value: Any, context: str) -> str:
    url = _optional_http_url(value, context)
    if url is None:
        raise FleetError(f"{context} must be a public HTTPS URL")
    return url


def _require_bool(value: Any, context: str, *, default: bool | None = None) -> bool:
    if value is None and default is not None:
        return default
    if not isinstance(value, bool):
        raise FleetError(f"{context} must be a boolean")
    return value


def _parse_evidence(value: Any, context: str) -> tuple[EvidenceSpec, ...]:
    if not isinstance(value, list):
        raise FleetError(f"{context} must be an array")
    result: list[EvidenceSpec] = []
    for index, item in enumerate(value):
        evidence_context = f"{context}[{index}]"
        table = _require_mapping(item, evidence_context)
        _reject_unknown_keys(table, {"label", "status", "url"}, evidence_context)
        status = _require_string(table.get("status"), f"{evidence_context}.status")
        if status not in EVIDENCE_STATUSES:
            raise FleetError(
                f"{evidence_context}.status must be one of: "
                + ", ".join(sorted(EVIDENCE_STATUSES))
            )
        result.append(
            EvidenceSpec(
                label=_require_string(table.get("label"), f"{evidence_context}.label"),
                status=status,
                url=_require_https_url(table.get("url"), f"{evidence_context}.url"),
            )
        )
    return tuple(result)


def _string_tuple(value: Any, context: str, *, nonempty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise FleetError(f"{context} must be an array of non-empty strings")
    if nonempty and not value:
        raise FleetError(f"{context} must not be empty")
    return tuple(value)


def _optional_branch(value: Any, context: str) -> str | None:
    branch = _optional_string(value, context)
    if branch is None:
        return None
    if (
        branch.startswith("-")
        or branch.endswith((".", "/"))
        or ".." in branch
        or "@{" in branch
        or re.search(r"[\s~^:?*\[\\]", branch)
    ):
        raise FleetError(f"{context} is not a safe Git branch name")
    return branch


def _optional_sha(value: Any, context: str) -> str | None:
    revision = _optional_string(value, context)
    if revision is not None and not re.fullmatch(r"[0-9a-fA-F]{40}", revision):
        raise FleetError(f"{context} must be a full 40-character commit SHA")
    return revision


def _validate_id(value: str, context: str) -> str:
    if not ID_PATTERN.fullmatch(value):
        raise FleetError(f"{context} has an invalid id: {value!r}")
    return value


def _validate_checkout(value: str, context: str) -> str:
    path = PurePosixPath(value.replace("\\", "/"))
    if path.is_absolute() or len(path.parts) != 1 or path.parts[0] in {".", ".."}:
        raise FleetError(f"{context} must be one directory name, got {value!r}")
    return value


def load_manifest(path: str | Path) -> Manifest:
    manifest_path = Path(path).expanduser().resolve()
    try:
        raw = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FleetError(f"manifest not found: {manifest_path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise FleetError(f"invalid TOML in {manifest_path}: {exc}") from exc

    _reject_unknown_keys(
        raw, {"schema", "fleet", "repositories", "next_actions", "mirrors"}, "manifest"
    )
    if raw.get("schema") != 1:
        raise FleetError("fleet manifest schema must be 1")
    fleet = _require_mapping(raw.get("fleet"), "fleet")
    _reject_unknown_keys(fleet, {"owner", "workspace"}, "fleet")
    owner = _require_string(fleet.get("owner"), "fleet.owner")
    workspace_value = _require_string(fleet.get("workspace", ".."), "fleet.workspace")
    default_workspace = (manifest_path.parent / workspace_value).resolve()

    repositories: dict[str, RepositorySpec] = {}
    raw_repositories = raw.get("repositories")
    if not isinstance(raw_repositories, list) or not raw_repositories:
        raise FleetError("repositories must be a non-empty array of tables")

    for index, item in enumerate(raw_repositories):
        table = _require_mapping(item, f"repositories[{index}]")
        _reject_unknown_keys(
            table,
            {
                "id", "github", "checkout", "default_branch", "maintenance_branch",
                "architecture", "modules", "tags", "required_globs", "rollout_order",
                "ci", "rollout_enabled", "allow_external",
            },
            f"repositories[{index}]",
        )
        repo_id = _validate_id(
            _require_string(table.get("id"), f"repositories[{index}].id"),
            f"repositories[{index}]",
        )
        if repo_id in repositories:
            raise FleetError(f"duplicate repository id: {repo_id}")
        checkout = _validate_checkout(
            _require_string(table.get("checkout"), f"repositories[{index}].checkout"),
            f"repositories[{index}].checkout",
        )
        github_value = table.get("github")
        github = None
        if github_value is not None:
            github = _require_string(github_value, f"repositories[{index}].github")
            if not GITHUB_PATTERN.fullmatch(github):
                raise FleetError(f"invalid GitHub repository name: {github!r}")
        ci = _require_bool(table.get("ci"), f"repositories[{index}].ci", default=True)
        if ci and github is None:
            raise FleetError(f"repository {repo_id!r} is enabled for CI but has no github value")
        rollout_enabled = _require_bool(
            table.get("rollout_enabled"),
            f"repositories[{index}].rollout_enabled",
            default=False,
        )
        allow_external = _require_bool(
            table.get("allow_external"),
            f"repositories[{index}].allow_external",
            default=False,
        )
        rollout_order = table.get("rollout_order")
        if rollout_order is not None and (
            not isinstance(rollout_order, int)
            or isinstance(rollout_order, bool)
            or rollout_order < 1
        ):
            raise FleetError(f"repositories[{index}].rollout_order must be a positive integer")

        default_branch = _optional_branch(
            table.get("default_branch"), f"repositories[{index}].default_branch"
        )
        if default_branch is None:
            raise FleetError(f"repositories[{index}].default_branch must be a non-empty string")
        maintenance_branch = _optional_branch(
            table.get("maintenance_branch", default_branch),
            f"repositories[{index}].maintenance_branch",
        )
        assert maintenance_branch is not None
        if github is not None:
            github_owner = github.split("/", 1)[0].casefold()
            if github_owner != owner.casefold() and not allow_external:
                raise FleetError(
                    f"repository {repo_id!r} belongs to external owner {github_owner!r}; "
                    "set allow_external = true explicitly"
                )
        if rollout_enabled:
            if github is None:
                raise FleetError(f"repository {repo_id!r} enables rollout without github")
            if "maintenance_branch" not in table:
                raise FleetError(
                    f"repository {repo_id!r} enables rollout without an explicit maintenance_branch"
                )
            if maintenance_branch == default_branch:
                raise FleetError(
                    f"repository {repo_id!r} rollout maintenance_branch must differ from "
                    "default_branch"
                )

        repositories[repo_id] = RepositorySpec(
            id=repo_id,
            checkout=checkout,
            default_branch=default_branch,
            maintenance_branch=maintenance_branch,
            architecture=_require_string(
                table.get("architecture"), f"repositories[{index}].architecture"
            ),
            modules=_string_tuple(table.get("modules", []), f"repositories[{index}].modules"),
            tags=_string_tuple(table.get("tags", []), f"repositories[{index}].tags"),
            required_globs=_string_tuple(
                table.get("required_globs", []), f"repositories[{index}].required_globs", nonempty=True
            ),
            rollout_order=rollout_order,
            github=github,
            ci=ci,
            rollout_enabled=rollout_enabled,
            allow_external=allow_external,
        )

    next_actions: list[NextActionSpec] = []
    seen_next_actions: set[str] = set()
    for index, item in enumerate(raw.get("next_actions", [])):
        table = _require_mapping(item, f"next_actions[{index}]")
        _reject_unknown_keys(
            table,
            {
                "id", "state", "priority", "order", "repository", "action", "completion",
                "blocker", "pr", "repository_url", "change_id", "validation_keys",
                "variant_ids", "evidence",
            },
            f"next_actions[{index}]",
        )
        action_id = _validate_id(
            _require_string(table.get("id"), f"next_actions[{index}].id"),
            f"next_actions[{index}]",
        )
        if action_id in seen_next_actions:
            raise FleetError(f"duplicate next action id: {action_id}")
        seen_next_actions.add(action_id)
        state = _require_string(table.get("state"), f"next_actions[{index}].state")
        if state not in NEXT_ACTION_STATES:
            allowed = ", ".join(sorted(NEXT_ACTION_STATES))
            raise FleetError(f"next_actions[{index}].state must be one of: {allowed}")
        priority = _require_string(
            table.get("priority"), f"next_actions[{index}].priority"
        )
        if priority not in NEXT_ACTION_PRIORITIES:
            allowed = ", ".join(sorted(NEXT_ACTION_PRIORITIES))
            raise FleetError(f"next_actions[{index}].priority must be one of: {allowed}")
        order = table.get("order")
        if not isinstance(order, int) or isinstance(order, bool) or order < 1:
            raise FleetError(f"next_actions[{index}].order must be a positive integer")
        validation_keys = _string_tuple(
            table.get("validation_keys", []), f"next_actions[{index}].validation_keys"
        )
        variant_ids = _string_tuple(
            table.get("variant_ids", []), f"next_actions[{index}].variant_ids"
        )
        for field_name, values in (("validation_keys", validation_keys), ("variant_ids", variant_ids)):
            if len(values) != len(set(values)):
                raise FleetError(f"next_actions[{index}].{field_name} contains duplicates")
            for value in values:
                _validate_id(value, f"next_actions[{index}].{field_name}")
        next_actions.append(
            NextActionSpec(
                id=action_id,
                state=state,
                priority=priority,
                order=order,
                repository=_require_string(
                    table.get("repository"), f"next_actions[{index}].repository"
                ),
                action=_require_string(table.get("action"), f"next_actions[{index}].action"),
                completion=_require_string(
                    table.get("completion"), f"next_actions[{index}].completion"
                ),
                blocker=_require_string(
                    table.get("blocker", ""),
                    f"next_actions[{index}].blocker",
                    allow_empty=True,
                ),
                pr=_optional_http_url(table.get("pr"), f"next_actions[{index}].pr"),
                repository_url=_optional_http_url(
                    table.get("repository_url"),
                    f"next_actions[{index}].repository_url",
                ),
                change_id=(
                    _validate_id(
                        _require_string(
                            table.get("change_id"), f"next_actions[{index}].change_id"
                        ),
                        f"next_actions[{index}].change_id",
                    )
                    if table.get("change_id") is not None
                    else None
                ),
                validation_keys=validation_keys,
                variant_ids=variant_ids,
                evidence=_parse_evidence(
                    table.get("evidence", []), f"next_actions[{index}].evidence"
                ),
            )
        )

    mirrors: list[MirrorSpec] = []
    seen_mirrors: set[str] = set()
    for index, item in enumerate(raw.get("mirrors", [])):
        table = _require_mapping(item, f"mirrors[{index}]")
        _reject_unknown_keys(
            table, {"id", "description", "enforce", "members"}, f"mirrors[{index}]"
        )
        mirror_id = _validate_id(
            _require_string(table.get("id"), f"mirrors[{index}].id"), f"mirrors[{index}]"
        )
        if mirror_id in seen_mirrors:
            raise FleetError(f"duplicate mirror id: {mirror_id}")
        seen_mirrors.add(mirror_id)
        raw_members = table.get("members")
        if not isinstance(raw_members, list) or len(raw_members) < 2:
            raise FleetError(f"mirror {mirror_id!r} must contain at least two members")
        members: list[MirrorMember] = []
        for member_index, member_item in enumerate(raw_members):
            member = _require_mapping(member_item, f"mirrors[{index}].members[{member_index}]")
            _reject_unknown_keys(
                member,
                {"repository", "path", "include", "exclude"},
                f"mirrors[{index}].members[{member_index}]",
            )
            repository = _require_string(
                member.get("repository"), f"mirrors[{index}].members[{member_index}].repository"
            )
            if repository not in repositories:
                raise FleetError(f"mirror {mirror_id!r} references unknown repository {repository!r}")
            members.append(
                MirrorMember(
                    repository=repository,
                    path=_require_string(
                        member.get("path"), f"mirrors[{index}].members[{member_index}].path"
                    ),
                    include=_string_tuple(
                        member.get("include", ["**"]),
                        f"mirrors[{index}].members[{member_index}].include",
                        nonempty=True,
                    ),
                    exclude=_string_tuple(
                        member.get("exclude", []),
                        f"mirrors[{index}].members[{member_index}].exclude",
                    ),
                )
            )
        enforce = table.get("enforce", False)
        if not isinstance(enforce, bool):
            raise FleetError(f"mirrors[{index}].enforce must be a boolean")
        mirrors.append(
            MirrorSpec(
                id=mirror_id,
                description=_require_string(
                    table.get("description", ""), f"mirrors[{index}].description", allow_empty=True
                ),
                enforce=enforce,
                members=tuple(members),
            )
        )

    return Manifest(
        path=manifest_path,
        owner=owner,
        default_workspace=default_workspace,
        repositories=repositories,
        mirrors=tuple(mirrors),
        next_actions=tuple(sorted(next_actions, key=lambda action: (action.order, action.id))),
    )


def resolve_workspace(manifest: Manifest, override: str | Path | None) -> Path:
    if override is None:
        return manifest.default_workspace
    return Path(override).expanduser().resolve()


def select_repositories(
    manifest: Manifest,
    repository_ids: Sequence[str] | None = None,
    tags: Sequence[str] | None = None,
    *,
    ci_only: bool = False,
) -> tuple[RepositorySpec, ...]:
    requested = set(repository_ids or ())
    unknown = requested.difference(manifest.repositories)
    if unknown:
        raise FleetError(f"unknown repository id(s): {', '.join(sorted(unknown))}")
    required_tags = set(tags or ())
    selected = []
    for repo in manifest.repositories.values():
        if requested and repo.id not in requested:
            continue
        if ci_only and not repo.ci:
            continue
        if required_tags and not required_tags.issubset(repo.tags):
            continue
        selected.append(repo)
    if requested and not selected:
        raise FleetError("repository filters selected no repositories")
    return tuple(selected)


def repository_path(workspace: Path, repo: RepositorySpec) -> Path:
    root = workspace.resolve()
    target = (root / repo.checkout).resolve()
    if target.parent != root:
        raise FleetError(f"unsafe checkout path for {repo.id}: {target}")
    return target


def _run_git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise FleetError(f"git {' '.join(args)} failed in {root}: {detail}")
    return result


def git_status(root: Path) -> tuple[bool, str]:
    probe = _run_git(root, "rev-parse", "--is-inside-work-tree", check=False)
    if probe.returncode != 0 or probe.stdout.strip() != "true":
        return False, "not-git"
    status = _run_git(root, "status", "--porcelain", "--untracked-files=normal").stdout
    return True, "dirty" if status.strip() else "clean"


def current_branch(root: Path) -> str:
    result = _run_git(root, "branch", "--show-current", check=False)
    return result.stdout.strip() or "(detached/unborn)"


def _checkout_contract_errors(
    repo: RepositorySpec,
    root: Path,
    *,
    allow_checkout_mismatch: bool = False,
    allow_default_branch: bool = False,
) -> tuple[str, ...]:
    errors: list[str] = []
    is_git, _ = git_status(root)
    if not is_git:
        return ("not a Git repository",)
    if repo.github:
        remote = _run_git(root, "remote", "get-url", "origin", check=False)
        if remote.returncode != 0:
            errors.append("origin remote is missing")
        elif _normalize_remote(remote.stdout) != _normalize_remote(repo.github):
            errors.append(
                f"origin mismatch: expected {repo.github}, found {remote.stdout.strip()}"
            )
    branch = current_branch(root)
    if branch != repo.maintenance_branch:
        errors.append(
            f"branch mismatch: expected maintenance branch {repo.maintenance_branch!r}, "
            f"found {branch!r}"
        )
    if branch == repo.default_branch and not allow_default_branch:
        errors.append(
            f"current branch {branch!r} is the stable/default branch; explicit override required"
        )
    if allow_checkout_mismatch:
        errors = [message for message in errors if not message.startswith(("origin ", "branch "))]
    return tuple(errors)


def _verify_checkout_contract(
    repo: RepositorySpec,
    root: Path,
    *,
    allow_checkout_mismatch: bool = False,
    allow_default_branch: bool = False,
) -> None:
    errors = _checkout_contract_errors(
        repo,
        root,
        allow_checkout_mismatch=allow_checkout_mismatch,
        allow_default_branch=allow_default_branch,
    )
    if errors:
        raise FleetError(f"unsafe checkout for {repo.id}: " + "; ".join(errors))


def _normalize_remote(value: str) -> str:
    remote = value.strip().removesuffix(".git")
    remote = re.sub(r"^git@github\.com:", "github.com/", remote)
    remote = re.sub(r"^(?:https?|git)://github\.com/", "github.com/", remote)
    if GITHUB_PATTERN.fullmatch(remote):
        remote = f"github.com/{remote}"
    return remote.lower().rstrip("/")


def inventory_rows(
    manifest: Manifest, workspace: Path, repositories: Sequence[RepositorySpec]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for repo in repositories:
        root = repository_path(workspace, repo)
        if not root.exists():
            git_state = "missing"
            branch = "-"
        else:
            is_git, git_state = git_status(root)
            branch = current_branch(root) if is_git else "-"
        rows.append(
            {
                "id": repo.id,
                "architecture": repo.architecture,
                "rollout_order": repo.rollout_order,
                "modules": list(repo.modules),
                "branch": branch,
                "state": git_state,
                "ci": repo.ci,
                "rollout_enabled": repo.rollout_enabled,
                "allow_external": repo.allow_external,
                "github": repo.github,
                "path": str(root),
            }
        )
    return rows


def revision_findings(
    workspace: Path,
    repositories: Sequence[RepositorySpec],
    *,
    strict_sha: bool = False,
) -> tuple[RevisionFinding, ...]:
    findings: list[RevisionFinding] = []
    moving_names = {"main", "master", "develop", "development", "dev", "latest", "head"}
    for repo in repositories:
        root = repository_path(workspace, repo)
        manifest_path = next(
            (candidate for candidate in (root / "config" / "west.yml", root / "west.yml") if candidate.is_file()),
            None,
        )
        if manifest_path is None:
            continue
        for line_number, line in enumerate(manifest_path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            match = re.match(r"revision:\s*([^#\s]+)", stripped, re.IGNORECASE)
            if not match:
                continue
            revision = match.group(1)
            if re.fullmatch(r"[0-9a-fA-F]{40}", revision):
                continue
            lowered = revision.lower()
            if re.fullmatch(r"[0-9a-fA-F]{4,39}", revision):
                kind = "short-sha"
            elif lowered in moving_names or "branch" in lowered or lowered.startswith("refs/heads/"):
                kind = "moving-ref"
            elif strict_sha:
                kind = "tag-or-ref"
            else:
                continue
            findings.append(
                RevisionFinding(
                    repository=repo.id,
                    path=manifest_path.relative_to(root).as_posix(),
                    line=line_number,
                    revision=revision,
                    kind=kind,
                )
            )
    return tuple(findings)


def revision_baseline_issues(
    entry: LedgerEntry,
    findings: Sequence[RevisionFinding],
    repositories: Sequence[RepositorySpec],
) -> tuple[AuditIssue, ...]:
    counts = {repo.id: 0 for repo in repositories}
    for finding in findings:
        if finding.repository in counts:
            counts[finding.repository] += 1
    issues: list[AuditIssue] = []
    for repo_id, count in counts.items():
        target = entry.tracking.get(repo_id)
        if target is None or target.findings is None:
            issues.append(
                AuditIssue("error", repo_id, "revision baseline has no typed findings count")
            )
            continue
        if count > target.findings:
            issues.append(
                AuditIssue(
                    "error",
                    repo_id,
                    f"moving revision count increased from {target.findings} to {count}",
                )
            )
    return tuple(issues)


def _matches_required_glob(root: Path, pattern: str) -> bool:
    for candidate in root.glob(pattern):
        if candidate.is_file():
            return True
    return False


def _collect_mirror_files(root: Path, member: MirrorMember) -> dict[str, str]:
    base = (root / member.path).resolve()
    if not base.is_relative_to(root.resolve()) or not base.is_dir():
        return {}
    files: dict[str, str] = {}
    for candidate in base.rglob("*"):
        if not candidate.is_file():
            continue
        resolved = candidate.resolve()
        if not resolved.is_relative_to(base):
            continue
        relative = candidate.relative_to(base).as_posix()
        if not any(fnmatch.fnmatchcase(relative, pattern) for pattern in member.include):
            continue
        if any(fnmatch.fnmatchcase(relative, pattern) for pattern in member.exclude):
            continue
        content = candidate.read_bytes().replace(b"\r\n", b"\n")
        files[relative] = hashlib.sha256(content).hexdigest()
    return files


def audit_fleet(
    manifest: Manifest,
    workspace: Path,
    repositories: Sequence[RepositorySpec],
) -> tuple[AuditIssue, ...]:
    issues: list[AuditIssue] = []
    selected_ids = {repo.id for repo in repositories}
    available: set[str] = set()

    for repo in repositories:
        root = repository_path(workspace, repo)
        if not root.exists():
            issues.append(AuditIssue("error", repo.id, f"checkout is missing: {root}"))
            continue
        is_git, state = git_status(root)
        if not is_git:
            issues.append(AuditIssue("error", repo.id, f"not a Git repository: {root}"))
            continue
        available.add(repo.id)
        if state == "dirty":
            issues.append(AuditIssue("warning", repo.id, "working tree has local changes"))

        if repo.github:
            remote = _run_git(root, "remote", "get-url", "origin", check=False)
            if remote.returncode != 0:
                issues.append(AuditIssue("error", repo.id, "origin remote is missing"))
            elif _normalize_remote(remote.stdout) != _normalize_remote(repo.github):
                issues.append(
                    AuditIssue(
                        "error",
                        repo.id,
                        f"origin mismatch: expected {repo.github}, found {remote.stdout.strip()}",
                    )
                )

        branch = current_branch(root)
        if branch != repo.maintenance_branch:
            issues.append(
                AuditIssue(
                    "error",
                    repo.id,
                    f"branch mismatch: expected maintenance branch "
                    f"{repo.maintenance_branch!r}, found {branch!r}",
                )
            )

        for pattern in repo.required_globs:
            if not _matches_required_glob(root, pattern):
                issues.append(
                    AuditIssue("error", repo.id, f"required file pattern matched nothing: {pattern}")
                )

    for mirror in manifest.mirrors:
        member_ids = {member.repository for member in mirror.members}
        if not member_ids.issubset(selected_ids) or not member_ids.issubset(available):
            continue
        baseline_member = mirror.members[0]
        baseline_root = repository_path(workspace, manifest.repositories[baseline_member.repository])
        baseline = _collect_mirror_files(baseline_root, baseline_member)
        if not baseline:
            issues.append(AuditIssue("error", mirror.id, "baseline mirror member contains no files"))
            continue
        for member in mirror.members[1:]:
            member_root = repository_path(workspace, manifest.repositories[member.repository])
            compared = _collect_mirror_files(member_root, member)
            differing = sorted(
                path for path in set(baseline) | set(compared) if baseline.get(path) != compared.get(path)
            )
            if differing:
                preview = ", ".join(differing[:8])
                if len(differing) > 8:
                    preview += f", ... (+{len(differing) - 8})"
                issues.append(
                    AuditIssue(
                        "error" if mirror.enforce else "warning",
                        mirror.id,
                        f"{baseline_member.repository} and {member.repository} differ: {preview}",
                    )
                )
    return tuple(issues)


def clone_repositories(
    manifest: Manifest,
    workspace: Path,
    repositories: Sequence[RepositorySpec],
    *,
    depth: int | None = 1,
) -> tuple[str, ...]:
    workspace.mkdir(parents=True, exist_ok=True)
    messages: list[str] = []
    for repo in repositories:
        target = repository_path(workspace, repo)
        if target.exists():
            messages.append(f"skip {repo.id}: {target} already exists")
            continue
        if repo.clone_url is None:
            messages.append(f"skip {repo.id}: local-only repository")
            continue
        command = ["git", "clone", "--single-branch", "--branch", repo.maintenance_branch]
        if depth is not None:
            command.extend(["--depth", str(depth)])
        command.extend([repo.clone_url, str(target)])
        result = subprocess.run(command, text=True, capture_output=True, check=False)
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip()
            raise FleetError(f"clone failed for {repo.id}: {detail}")
        messages.append(f"cloned {repo.id}: {target}")
    return tuple(messages)


def _parse_expectation(value: Any, context: str) -> Expectation:
    if isinstance(value, bool):
        raise FleetError(f"{context} must be an integer or min/max object")
    if isinstance(value, int):
        if value < 0:
            raise FleetError(f"{context} must not be negative")
        return Expectation(value, value)
    table = _require_mapping(value, context)
    _reject_unknown_keys(table, {"min", "max"}, context)
    minimum = table.get("min")
    maximum = table.get("max")
    if (
        isinstance(minimum, bool)
        or isinstance(maximum, bool)
        or not isinstance(minimum, int)
        or not isinstance(maximum, int)
        or minimum < 0
        or maximum < minimum
    ):
        raise FleetError(f"{context} must contain integers with 0 <= min <= max")
    return Expectation(minimum, maximum)


def resolve_campaign_path(manifest: Manifest, source: str | Path) -> Path:
    value = Path(source)
    if value.exists():
        return value.expanduser().resolve()
    source_text = str(source)
    if not ID_PATTERN.fullmatch(source_text):
        raise FleetError(f"campaign must be a safe id or existing JSON path: {source_text!r}")
    change_path = (manifest.path.parent / "changes" / f"{source_text}.json").resolve()
    if change_path.exists():
        return change_path
    return (manifest.path.parent / "campaigns" / f"{source_text}.json").resolve()


def load_campaign(
    manifest: Manifest, source: str | Path, *, allow_disabled: bool = False
) -> Campaign:
    campaign_path = resolve_campaign_path(manifest, source)
    try:
        raw = json.loads(campaign_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FleetError(f"campaign not found: {campaign_path}") from exc
    except json.JSONDecodeError as exc:
        raise FleetError(f"invalid JSON in {campaign_path}: {exc}") from exc
    table = _require_mapping(raw, "campaign")
    _reject_unknown_keys(
        table,
        {
            "schema", "id", "enabled", "title", "description", "repositories", "steps",
            "source", "trigger", "scope", "tracking", "metrics", "dashboard_label",
        },
        "campaign",
    )
    if table.get("schema") != 1:
        raise FleetError("campaign schema must be 1")
    campaign_id = _validate_id(_require_string(table.get("id"), "campaign.id"), "campaign")
    if campaign_path.suffix == ".json" and campaign_path.stem != campaign_id:
        raise FleetError(
            f"campaign filename must match its id: {campaign_path.stem!r} != {campaign_id!r}"
        )
    enabled = table.get("enabled", False)
    if not isinstance(enabled, bool):
        raise FleetError("campaign.enabled must be a boolean")
    if not enabled and not allow_disabled:
        raise FleetError(f"campaign {campaign_id!r} is disabled")
    repository_ids = _string_tuple(table.get("repositories"), "campaign.repositories", nonempty=True)
    if len(repository_ids) != len(set(repository_ids)):
        raise FleetError("campaign.repositories contains duplicates")
    unknown = set(repository_ids).difference(manifest.repositories)
    if unknown:
        raise FleetError(f"campaign references unknown repositories: {', '.join(sorted(unknown))}")

    raw_steps = table.get("steps", [])
    if not isinstance(raw_steps, list):
        raise FleetError("campaign.steps must be an array")
    steps: list[CampaignStep] = []
    seen_step_ids: set[str] = set()
    for index, item in enumerate(raw_steps):
        step = _require_mapping(item, f"campaign.steps[{index}]")
        _reject_unknown_keys(
            step,
            {
                "id", "repositories", "paths", "operation", "find", "replace", "expect",
                "flags", "already_pattern",
            },
            f"campaign.steps[{index}]",
        )
        step_id = _validate_id(
            _require_string(step.get("id"), f"campaign.steps[{index}].id"),
            f"campaign.steps[{index}]",
        )
        if step_id in seen_step_ids:
            raise FleetError(f"duplicate campaign step id: {step_id}")
        seen_step_ids.add(step_id)
        step_repositories = _string_tuple(
            step.get("repositories", list(repository_ids)),
            f"campaign.steps[{index}].repositories",
            nonempty=True,
        )
        if len(step_repositories) != len(set(step_repositories)):
            raise FleetError(f"step {step_id!r} contains duplicate repositories")
        if not set(step_repositories).issubset(repository_ids):
            raise FleetError(f"step {step_id!r} targets a repository outside campaign.repositories")
        operation = _require_string(step.get("operation"), f"campaign.steps[{index}].operation")
        if operation not in {"literal_replace", "regex_replace"}:
            raise FleetError(f"step {step_id!r} has unsupported operation {operation!r}")
        find = _require_string(step.get("find"), f"campaign.steps[{index}].find")
        replacement = _require_string(step.get("replace"), f"campaign.steps[{index}].replace")
        if operation == "literal_replace" and find in replacement:
            raise FleetError(
                f"step {step_id!r} replacement contains the old literal and is not safely idempotent"
            )
        flags = _string_tuple(step.get("flags", []), f"campaign.steps[{index}].flags")
        allowed_flags = {"IGNORECASE", "MULTILINE", "DOTALL"}
        if not set(flags).issubset(allowed_flags):
            raise FleetError(f"step {step_id!r} uses unsupported regex flags")
        already_pattern = step.get("already_pattern")
        if operation == "regex_replace":
            if already_pattern is None:
                raise FleetError(f"regex step {step_id!r} requires already_pattern")
            already_pattern = _require_string(
                already_pattern, f"campaign.steps[{index}].already_pattern"
            )
        expect_table = _require_mapping(step.get("expect"), f"campaign.steps[{index}].expect")
        missing_expectations = set(step_repositories).difference(expect_table)
        extra_expectations = set(expect_table).difference(step_repositories)
        if missing_expectations or extra_expectations:
            raise FleetError(
                f"step {step_id!r} expectation keys must exactly match its repositories"
            )
        expectations = {
            repo_id: _parse_expectation(expect_table[repo_id], f"step {step_id}.expect.{repo_id}")
            for repo_id in step_repositories
        }
        steps.append(
            CampaignStep(
                id=step_id,
                repositories=step_repositories,
                paths=_string_tuple(
                    step.get("paths"), f"campaign.steps[{index}].paths", nonempty=True
                ),
                operation=operation,
                find=find,
                replace=replacement,
                expect=expectations,
                flags=flags,
                already_pattern=already_pattern,
            )
        )

    return Campaign(
        path=campaign_path,
        id=campaign_id,
        title=_require_string(table.get("title"), "campaign.title"),
        description=_require_string(
            table.get("description", ""), "campaign.description", allow_empty=True
        ),
        enabled=enabled,
        repositories=repository_ids,
        steps=tuple(steps),
    )


def _parse_validation(
    value: Any, context: str
) -> dict[str, str]:
    table = _require_mapping(value, context)
    result: dict[str, str] = {}
    for check_name, status_value in table.items():
        check_id = _validate_id(_require_string(check_name, f"{context} key"), context)
        check_status = _require_string(status_value, f"{context}.{check_id}")
        if check_status not in VALIDATION_STATUSES:
            raise FleetError(
                f"{context}.{check_id} must be one of: "
                + ", ".join(sorted(VALIDATION_STATUSES))
            )
        result[check_id] = check_status
    return result


def _parse_validation_urls(
    value: Any, validation: Mapping[str, str], context: str
) -> dict[str, str]:
    table = _require_mapping(value, context)
    result: dict[str, str] = {}
    for check_name, url_value in table.items():
        check_id = _validate_id(_require_string(check_name, f"{context} key"), context)
        if check_id not in validation:
            raise FleetError(f"{context}.{check_id} has no matching validation check")
        result[check_id] = _optional_http_url(url_value, f"{context}.{check_id}") or ""
    return result


def _required_validation(
    value: Any, validation: Mapping[str, str], context: str
) -> tuple[str, ...]:
    required = _string_tuple(value, context)
    if len(required) != len(set(required)):
        raise FleetError(f"{context} contains duplicates")
    for check_id in required:
        _validate_id(check_id, context)
    missing = sorted(set(required).difference(validation))
    if missing:
        raise FleetError(f"{context} references unknown validation(s): {', '.join(missing)}")
    return required


def target_validation_complete(target: TargetTracking) -> bool:
    """Return completion using explicit gates; terminal status alone is insufficient."""
    if target.status == "not-applicable":
        return not target.validation and not target.variants
    if target.status not in {"merged", "applied"}:
        return False

    required = target.required_validation or tuple(target.validation)
    if not required and not target.variants:
        return False
    if any(target.validation.get(key) not in {"passed", "waived"} for key in required):
        return False
    for variant in target.variants:
        if variant.status != "passed":
            return False
        variant_required = tuple(variant.validation)
        if any(
            variant.validation.get(key) not in {"passed", "waived"}
            for key in variant_required
        ):
            return False
    return True


def load_ledger_entry(
    manifest: Manifest, source: str | Path, *, allow_disabled: bool = True
) -> LedgerEntry:
    campaign = load_campaign(manifest, source, allow_disabled=allow_disabled)
    try:
        raw = json.loads(campaign.path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:  # load_campaign normally catches these
        raise FleetError(f"cannot read ledger entry {campaign.path}: {exc}") from exc
    table = _require_mapping(raw, "change")
    _reject_unknown_keys(
        table,
        {
            "schema", "id", "enabled", "title", "description", "repositories", "steps",
            "source", "trigger", "scope", "tracking", "metrics", "dashboard_label",
        },
        "change",
    )
    metrics_info = None
    if table.get("metrics") is not None:
        metrics = _require_mapping(table.get("metrics"), "change.metrics")
        _reject_unknown_keys(
            metrics,
            {
                "finding_total", "measured_at", "fleet_commit", "audit_run",
                "measurement_mode", "measurement_command", "measurement_scope",
                "evidence_status", "local_only_baseline",
            },
            "change.metrics",
        )
        finding_total = metrics.get("finding_total")
        if finding_total is not None and (
            not isinstance(finding_total, int)
            or isinstance(finding_total, bool)
            or finding_total < 0
        ):
            raise FleetError("change.metrics.finding_total must be a non-negative integer")
        measured_at = _optional_string(metrics.get("measured_at"), "change.metrics.measured_at")
        if measured_at is not None and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", measured_at):
            raise FleetError("change.metrics.measured_at must use YYYY-MM-DD")
        measurement_mode = _optional_string(
            metrics.get("measurement_mode"), "change.metrics.measurement_mode"
        )
        if measurement_mode is not None and measurement_mode != "strict-sha":
            raise FleetError("change.metrics.measurement_mode must be strict-sha")
        measurement_command = _optional_string(
            metrics.get("measurement_command"), "change.metrics.measurement_command"
        )
        if measurement_command is not None:
            try:
                command_parts = shlex.split(measurement_command)
            except ValueError as exc:
                raise FleetError(
                    f"change.metrics.measurement_command is not a valid command: {exc}"
                ) from exc
            if (
                command_parts[:2] != ["shield-fleet", "revisions"]
                or "--strict-sha" not in command_parts
            ):
                raise FleetError(
                    "change.metrics.measurement_command must record a "
                    "shield-fleet revisions command with --strict-sha"
                )
        evidence_status = _optional_string(
            metrics.get("evidence_status"), "change.metrics.evidence_status"
        )
        if evidence_status is not None:
            _validate_id(evidence_status, "change.metrics.evidence_status")
        local_baseline_info = None
        if metrics.get("local_only_baseline") is not None:
            local_baseline = _require_mapping(
                metrics.get("local_only_baseline"), "change.metrics.local_only_baseline"
            )
            _reject_unknown_keys(
                local_baseline,
                {"repository", "findings", "status"},
                "change.metrics.local_only_baseline",
            )
            local_findings = local_baseline.get("findings")
            if (
                not isinstance(local_findings, int)
                or isinstance(local_findings, bool)
                or local_findings < 0
            ):
                raise FleetError(
                    "change.metrics.local_only_baseline.findings must be a non-negative integer"
                )
            local_baseline_info = LocalRevisionBaseline(
                repository=_require_string(
                    local_baseline.get("repository"),
                    "change.metrics.local_only_baseline.repository",
                ),
                findings=local_findings,
                status=_require_string(
                    local_baseline.get("status"),
                    "change.metrics.local_only_baseline.status",
                ),
            )
        metrics_info = RevisionMetrics(
            finding_total=finding_total,
            measured_at=measured_at,
            measurement_mode=measurement_mode,
            measurement_command=measurement_command,
            fleet_commit=_optional_sha(
                metrics.get("fleet_commit"), "change.metrics.fleet_commit"
            ),
            audit_run=_optional_http_url(metrics.get("audit_run"), "change.metrics.audit_run"),
            measurement_scope=_optional_string(
                metrics.get("measurement_scope"), "change.metrics.measurement_scope"
            ),
            evidence_status=evidence_status,
            local_only_baseline=local_baseline_info,
        )
    if table.get("dashboard_label") is not None:
        _require_string(table.get("dashboard_label"), "change.dashboard_label")
    source_table = _require_mapping(table.get("source"), "change.source")
    _reject_unknown_keys(
        source_table,
        {"repository", "from_revision", "to_revision", "change_url", "notes"},
        "change.source",
    )
    source_info = ChangeSource(
        repository=_require_string(source_table.get("repository"), "change.source.repository"),
        from_revision=_optional_string(
            source_table.get("from_revision"), "change.source.from_revision"
        ),
        to_revision=_require_string(source_table.get("to_revision"), "change.source.to_revision"),
        change_url=_optional_http_url(source_table.get("change_url"), "change.source.change_url"),
        notes=_require_string(
            source_table.get("notes", ""), "change.source.notes", allow_empty=True
        ),
    )
    trigger_info = None
    if table.get("trigger") is not None:
        trigger_table = _require_mapping(table.get("trigger"), "change.trigger")
        _reject_unknown_keys(
            trigger_table,
            {"repository", "revision", "change_url", "notes"},
            "change.trigger",
        )
        trigger_info = ChangeTrigger(
            repository=_require_string(
                trigger_table.get("repository"), "change.trigger.repository"
            ),
            revision=_require_string(trigger_table.get("revision"), "change.trigger.revision"),
            change_url=_require_https_url(
                trigger_table.get("change_url"), "change.trigger.change_url"
            ),
            notes=_require_string(
                trigger_table.get("notes", ""), "change.trigger.notes", allow_empty=True
            ),
        )
    scope_module = None
    scope_all = False
    if table.get("scope") is not None:
        scope_table = _require_mapping(table.get("scope"), "change.scope")
        if set(scope_table) == {"module"}:
            scope_module = _validate_id(
                _require_string(scope_table.get("module"), "change.scope.module"),
                "change.scope.module",
            )
            expected_repositories = {
                repo.id for repo in manifest.repositories.values() if scope_module in repo.modules
            }
            scope_description = repr(scope_module) + " consumer"
        elif set(scope_table) == {"all"} and scope_table.get("all") is True:
            scope_all = True
            expected_repositories = set(manifest.repositories)
            scope_description = "managed repository"
        else:
            raise FleetError("change.scope must be either {module: <id>} or {all: true}")
        if set(campaign.repositories) != expected_repositories:
            missing = sorted(expected_repositories.difference(campaign.repositories))
            extra = sorted(set(campaign.repositories).difference(expected_repositories))
            details = []
            if missing:
                details.append("missing " + ", ".join(missing))
            if extra:
                details.append("extra " + ", ".join(extra))
            raise FleetError(
                f"change.repositories must match every {scope_description}: "
                + "; ".join(details)
            )
    tracking_table = _require_mapping(table.get("tracking"), "change.tracking")
    if set(tracking_table) != set(campaign.repositories):
        raise FleetError("change.tracking keys must exactly match change.repositories")
    tracking: dict[str, TargetTracking] = {}
    for repo_id in campaign.repositories:
        context = f"change.tracking.{repo_id}"
        target = _require_mapping(tracking_table[repo_id], context)
        _reject_unknown_keys(
            target,
            {
                "status", "pr", "commit", "notes", "validation", "validation_urls",
                "branch", "base_branch", "pr_head", "required_validation", "variants",
                "findings",
            },
            context,
        )
        status = _require_string(target.get("status"), f"{context}.status")
        if status not in LEDGER_STATUSES:
            raise FleetError(
                f"{context}.status must be one of: "
                + ", ".join(sorted(LEDGER_STATUSES))
            )
        validation = _parse_validation(target.get("validation", {}), f"{context}.validation")
        validation_urls = _parse_validation_urls(
            target.get("validation_urls", {}), validation, f"{context}.validation_urls"
        )
        required_validation = _required_validation(
            target.get("required_validation", []), validation, f"{context}.required_validation"
        )
        variants_value = target.get("variants", [])
        if not isinstance(variants_value, list):
            raise FleetError(f"{context}.variants must be an array")
        variants: list[ValidationVariant] = []
        seen_variant_ids: set[str] = set()
        for variant_index, variant_value in enumerate(variants_value):
            variant_context = f"{context}.variants[{variant_index}]"
            variant = _require_mapping(variant_value, variant_context)
            _reject_unknown_keys(
                variant, {"id", "status", "validation", "evidence"}, variant_context
            )
            variant_id = _validate_id(
                _require_string(variant.get("id"), f"{variant_context}.id"), variant_context
            )
            if variant_id in seen_variant_ids:
                raise FleetError(f"{context}.variants contains duplicate id {variant_id!r}")
            seen_variant_ids.add(variant_id)
            variant_context = f"{context}.variants.{variant_id}"
            variant_status = _require_string(
                variant.get("status"), f"{variant_context}.status"
            )
            if variant_status not in {"passed", "pending"}:
                raise FleetError(f"{variant_context}.status must be passed or pending")
            variant_validation = _parse_validation(
                variant.get("validation", {}), f"{variant_context}.validation"
            )
            evidence = _parse_evidence(
                variant.get("evidence", []), f"{variant_context}.evidence"
            )
            if variant_status == "passed":
                incomplete_gates = sorted(
                    key
                    for key, gate_status in variant_validation.items()
                    if gate_status not in {"passed", "waived"}
                )
                incomplete_evidence = [
                    item.label for item in evidence if item.status in {"pending", "failed"}
                ]
                if incomplete_gates or incomplete_evidence:
                    details = incomplete_gates + incomplete_evidence
                    raise FleetError(
                        f"{variant_context} is passed but has incomplete evidence/gates: "
                        + ", ".join(details)
                    )
            variants.append(ValidationVariant(
                id=variant_id,
                status=variant_status,
                validation=variant_validation,
                evidence=evidence,
            ))
        findings = target.get("findings")
        if findings is not None and (
            not isinstance(findings, int) or isinstance(findings, bool) or findings < 0
        ):
            raise FleetError(f"{context}.findings must be a non-negative integer")
        if status == "not-applicable" and (
            validation or validation_urls or required_validation or variants
        ):
            raise FleetError(f"{context} is not-applicable but declares validation")
        tracking[repo_id] = TargetTracking(
            status=status,
            pr=_optional_http_url(target.get("pr"), f"{context}.pr"),
            commit=_optional_sha(target.get("commit"), f"{context}.commit"),
            notes=_require_string(
                target.get("notes", ""), f"{context}.notes", allow_empty=True
            ),
            validation=validation,
            validation_urls=validation_urls,
            branch=_optional_branch(target.get("branch"), f"{context}.branch"),
            base_branch=_optional_branch(target.get("base_branch"), f"{context}.base_branch"),
            pr_head=_optional_sha(target.get("pr_head"), f"{context}.pr_head"),
            required_validation=required_validation,
            variants=tuple(variants),
            findings=findings,
        )
    return LedgerEntry(
        campaign=campaign,
        source=source_info,
        trigger=trigger_info,
        scope_module=scope_module,
        scope_all=scope_all,
        tracking=tracking,
        metrics=metrics_info,
    )


def list_ledger_entries(manifest: Manifest) -> tuple[LedgerEntry, ...]:
    directory = manifest.path.parent / "changes"
    if not directory.exists():
        return ()
    entries = tuple(
        load_ledger_entry(manifest, path) for path in sorted(directory.glob("*.json"))
    )
    validate_next_action_references(manifest, entries)
    return entries


def validate_next_action_references(
    manifest: Manifest, entries: Sequence[LedgerEntry]
) -> None:
    by_id = {entry.campaign.id: entry for entry in entries}
    for action in manifest.next_actions:
        if (action.validation_keys or action.variant_ids) and action.change_id is None:
            raise FleetError(
                f"next action {action.id!r} references validation/variants without change_id"
            )
        if action.change_id is None:
            continue
        entry = by_id.get(action.change_id)
        if entry is None:
            raise FleetError(
                f"next action {action.id!r} references unknown change {action.change_id!r}"
            )
        group_ids = tuple(
            part.strip() for part in action.repository.split(" / ") if part.strip()
        )
        if " / " in action.repository:
            unknown_group_ids = sorted(set(group_ids).difference(entry.tracking))
            if unknown_group_ids:
                raise FleetError(
                    f"next action {action.id!r} repository group references unknown "
                    "target(s): " + ", ".join(unknown_group_ids)
                )
            group_checks: set[str] = set()
            group_variants: set[str] = set()
            for repo_id in group_ids:
                candidate = entry.tracking[repo_id]
                group_checks.update(candidate.validation)
                for variant in candidate.variants:
                    group_variants.add(variant.id)
                    group_checks.update(variant.validation)
            missing_group_checks = sorted(set(action.validation_keys).difference(group_checks))
            missing_group_variants = sorted(set(action.variant_ids).difference(group_variants))
            if missing_group_checks or missing_group_variants:
                details = missing_group_checks + missing_group_variants
                raise FleetError(
                    f"next action {action.id!r} repository group references unknown "
                    "validation/variant(s): " + ", ".join(details)
                )
            continue
        target = entry.tracking.get(action.repository)
        if target is None:
            if action.repository_url is None:
                raise FleetError(
                    f"next action {action.id!r} references repository {action.repository!r} "
                    f"outside change {action.change_id!r} without repository_url"
                )
            if not action.variant_ids:
                available_change_checks: set[str] = set()
                for candidate in entry.tracking.values():
                    available_change_checks.update(candidate.validation)
                    for variant in candidate.variants:
                        available_change_checks.update(variant.validation)
                missing_change_checks = sorted(
                    set(action.validation_keys).difference(available_change_checks)
                )
                if missing_change_checks:
                    raise FleetError(
                        f"next action {action.id!r} references unknown change-level "
                        "validation(s): " + ", ".join(missing_change_checks)
                    )
                continue
            candidates: list[TargetTracking] = []
            for candidate in entry.tracking.values():
                candidate_variants = {variant.id: variant for variant in candidate.variants}
                if not set(action.variant_ids).issubset(candidate_variants):
                    continue
                candidate_checks = set(candidate.validation)
                selected = (
                    [candidate_variants[variant_id] for variant_id in action.variant_ids]
                    if action.variant_ids
                    else candidate.variants
                )
                for variant in selected:
                    candidate_checks.update(variant.validation)
                if set(action.validation_keys).issubset(candidate_checks):
                    candidates.append(candidate)
            if len(candidates) != 1:
                raise FleetError(
                    f"next action {action.id!r} has an ambiguous external repository "
                    f"reference for change {action.change_id!r}: {len(candidates)} targets match"
                )
            target = candidates[0]
        variants_by_id = {variant.id: variant for variant in target.variants}
        available_checks = set(target.validation)
        selected_variants = (
            [variants_by_id[variant_id] for variant_id in action.variant_ids if variant_id in variants_by_id]
            if action.variant_ids
            else target.variants
        )
        for variant in selected_variants:
            available_checks.update(variant.validation)
        missing_checks = sorted(set(action.validation_keys).difference(available_checks))
        if missing_checks:
            raise FleetError(
                f"next action {action.id!r} references unknown validation(s): "
                + ", ".join(missing_checks)
            )
        missing_variants = sorted(
            set(action.variant_ids).difference(variants_by_id)
        )
        if missing_variants:
            raise FleetError(
                f"next action {action.id!r} references unknown variant(s): "
                + ", ".join(missing_variants)
            )


def mark_ledger_target(
    entry: LedgerEntry,
    repository: str,
    status: str,
    *,
    pr: str | None = None,
    commit: str | None = None,
    notes: str | None = None,
    validation: Mapping[str, str] | None = None,
    validation_urls: Mapping[str, str] | None = None,
) -> None:
    if repository not in entry.tracking:
        raise FleetError(f"repository {repository!r} is not tracked by change {entry.campaign.id!r}")
    if status not in LEDGER_STATUSES:
        raise FleetError(f"invalid ledger status: {status!r}")
    if pr:
        _optional_http_url(pr, "pull request URL")
    if commit:
        _optional_sha(commit, "commit")
    raw = json.loads(entry.path.read_text(encoding="utf-8"))
    target = raw["tracking"][repository]
    updated_validation = dict(target.get("validation", {}))
    if validation is not None:
        for check_id, check_status in validation.items():
            _validate_id(check_id, "validation")
            if check_status not in VALIDATION_STATUSES:
                raise FleetError(f"invalid validation status: {check_status!r}")
            updated_validation[check_id] = check_status
    updated_validation_urls = dict(target.get("validation_urls", {}))
    if validation_urls is not None:
        for check_id, url in validation_urls.items():
            _validate_id(check_id, "validation URL")
            if check_id not in updated_validation:
                raise FleetError(f"validation URL {check_id!r} has no matching validation check")
            if not re.fullmatch(r"https://[^\s]+", url):
                raise FleetError(f"validation URL {check_id!r} must use HTTPS")
            updated_validation_urls[check_id] = url
    if status == "not-applicable" and (
        updated_validation or entry.tracking[repository].variants
    ):
        raise FleetError("not-applicable targets cannot retain validation or variants")
    target["status"] = status
    if pr is not None:
        target["pr"] = pr or None
    if commit is not None:
        target["commit"] = commit or None
    if notes is not None:
        target["notes"] = notes
    if validation is not None:
        target["validation"] = updated_validation
    if validation_urls is not None:
        target["validation_urls"] = updated_validation_urls
    _write_json_atomic(entry.path, raw)


def _write_json_atomic(path: Path, value: Any) -> None:
    rendered = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(rendered)
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def github_pull_requests(
    repository: str, branch: str, base_branch: str | None = None
) -> list[dict[str, Any]]:
    command = [
        "gh", "pr", "list", "--repo", repository, "--head", branch, "--state", "all",
        "--limit", "20", "--json",
        "number,url,state,isDraft,mergedAt,mergeCommit,createdAt,updatedAt,baseRefName,headRefName,headRefOid",
    ]
    if base_branch:
        command[8:8] = ["--base", base_branch]
    try:
        result = subprocess.run(command, text=True, capture_output=True, check=False)
    except FileNotFoundError as exc:
        raise FleetError("gh is required for ledger sync") from exc
    if result.returncode != 0:
        raise FleetError(f"cannot query {repository}: {result.stderr.strip()}")
    return json.loads(result.stdout)


def github_pr_evidence(pr_url: str) -> Mapping[str, Any]:
    command = [
        "gh", "pr", "view", pr_url, "--json",
        "url,state,mergedAt,mergeCommit,baseRefName,headRefName,headRefOid,statusCheckRollup",
    ]
    try:
        result = subprocess.run(command, text=True, capture_output=True, check=False)
    except FileNotFoundError as exc:
        raise FleetError("gh is required for evidence audit") from exc
    if result.returncode != 0:
        raise FleetError(f"cannot inspect {pr_url}: {result.stderr.strip()}")
    return _require_mapping(json.loads(result.stdout), f"PR evidence {pr_url}")


def github_branch_evidence(repository: str, branch: str) -> Mapping[str, Any]:
    encoded_branch = urllib.parse.quote(branch, safe="")
    command = ["gh", "api", f"repos/{repository}/branches/{encoded_branch}"]
    try:
        result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError as exc:
        raise FleetError("gh is required for evidence audit") from exc
    if result.returncode != 0:
        raise FleetError(
            f"cannot inspect branch {repository}@{branch}: {result.stderr.strip()}"
        )
    return _require_mapping(json.loads(result.stdout), f"branch evidence {repository}@{branch}")


def evidence_audit(
    manifest: Manifest,
    entries: Sequence[LedgerEntry],
    *,
    fetcher=github_pr_evidence,
    branch_fetcher=github_branch_evidence,
) -> tuple[AuditIssue, ...]:
    """Read remote PR evidence without mutating either the ledger or repositories."""
    issues: list[AuditIssue] = []
    for entry in entries:
        for repo_id, target in entry.tracking.items():
            spec = manifest.repositories[repo_id]
            subject = f"{entry.campaign.id}/{repo_id}"
            if (
                target.branch
                and spec.github
                and target.status in {"pending", "pr-open"}
            ):
                try:
                    branch_evidence = branch_fetcher(spec.github, target.branch)
                except (FleetError, OSError, ValueError, json.JSONDecodeError) as exc:
                    issues.append(
                        AuditIssue("warning", subject, f"cannot verify tracked branch: {exc}")
                    )
                else:
                    branch_sha = (branch_evidence.get("commit") or {}).get("sha")
                    if target.pr_head and branch_sha not in {None, target.pr_head}:
                        issues.append(
                            AuditIssue(
                                "error", subject,
                                f"tracked branch SHA is {branch_sha!r}, expected {target.pr_head!r}",
                            )
                        )
            if target.pr is None:
                continue
            expected_prefix = f"https://github.com/{spec.github}/pull/" if spec.github else None
            if expected_prefix and not target.pr.startswith(expected_prefix):
                issues.append(
                    AuditIssue("error", subject, f"PR URL does not belong to {spec.github}")
                )
                continue
            try:
                evidence = fetcher(target.pr)
            except (FleetError, OSError, ValueError, json.JSONDecodeError) as exc:
                issues.append(AuditIssue("warning", subject, f"cannot verify PR evidence: {exc}"))
                continue
            if evidence.get("url") not in {None, target.pr}:
                issues.append(AuditIssue("error", subject, "PR evidence URL mismatch"))
            remote_state = evidence.get("state")
            expected_states = {
                "pr-open": {"OPEN"},
                "merged": {"MERGED"},
                "closed": {"CLOSED"},
            }.get(target.status)
            if expected_states and remote_state not in expected_states:
                issues.append(
                    AuditIssue(
                        "error",
                        subject,
                        f"ledger status {target.status!r} conflicts with PR state {remote_state!r}",
                    )
                )
            expected_base = target.base_branch or spec.maintenance_branch
            if evidence.get("baseRefName") not in {None, expected_base}:
                issues.append(
                    AuditIssue(
                        "error", subject,
                        f"PR base is {evidence.get('baseRefName')!r}, expected {expected_base!r}",
                    )
                )
            if target.branch and evidence.get("headRefName") not in {None, target.branch}:
                issues.append(
                    AuditIssue(
                        "error", subject,
                        f"PR head branch is {evidence.get('headRefName')!r}, "
                        f"expected {target.branch!r}",
                    )
                )
            if target.pr_head and evidence.get("headRefOid") not in {None, target.pr_head}:
                issues.append(
                    AuditIssue(
                        "error", subject,
                        f"PR head SHA is {evidence.get('headRefOid')!r}, "
                        f"expected {target.pr_head!r}",
                    )
                )
            checks = evidence.get("statusCheckRollup") or []
            conclusions = {
                str(check.get("conclusion") or check.get("state") or "").upper()
                for check in checks
                if isinstance(check, dict)
            }
            failed = conclusions.intersection(
                {"FAILURE", "ERROR", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED"}
            )
            ledger_ci_passed = any(
                status == "passed"
                and (key == "ci" or key.endswith("-ci") or "build" in key)
                for key, status in target.validation.items()
            )
            if ledger_ci_passed and failed:
                issues.append(
                    AuditIssue(
                        "error", subject,
                        "ledger marks CI passed but PR checks contain: " + ", ".join(sorted(failed)),
                    )
                )
    return tuple(issues)


def sync_ledger_entry(
    manifest: Manifest,
    entry: LedgerEntry,
    *,
    write: bool = False,
    fetcher=github_pull_requests,
) -> Mapping[str, TargetTracking]:
    updated = dict(entry.tracking)
    raw = json.loads(entry.path.read_text(encoding="utf-8")) if write else None
    for repo_id, current in entry.tracking.items():
        if current.status == "not-applicable":
            continue
        spec = manifest.repositories[repo_id]
        if spec.github is None:
            continue
        head_branch = current.branch or f"fleet/{entry.campaign.id}"
        base_branch = current.base_branch or spec.maintenance_branch
        pulls = fetcher(spec.github, head_branch, base_branch)
        if not pulls:
            continue
        if len(pulls) != 1:
            urls = ", ".join(str(item.get("url") or item.get("number")) for item in pulls)
            raise FleetError(
                f"multiple PR candidates for {repo_id} head {head_branch!r} "
                f"base {base_branch!r}: {urls}"
            )
        pull = pulls[0]
        if pull.get("headRefName") not in {None, head_branch}:
            raise FleetError(
                f"PR candidate head mismatch for {repo_id}: {pull.get('headRefName')!r}"
            )
        if pull.get("baseRefName") not in {None, base_branch}:
            raise FleetError(
                f"PR candidate base mismatch for {repo_id}: {pull.get('baseRefName')!r}"
            )
        if current.pr_head and pull.get("headRefOid") != current.pr_head:
            raise FleetError(
                f"PR candidate head SHA mismatch for {repo_id}: "
                f"expected {current.pr_head}, found {pull.get('headRefOid')}"
            )
        if pull.get("mergedAt"):
            status = "merged"
        elif pull.get("state") == "OPEN":
            status = "pr-open"
        else:
            status = "closed"
        merge_commit = pull.get("mergeCommit") or {}
        pr_url = pull.get("url") or current.pr
        if pr_url:
            pr_url = _require_https_url(pr_url, f"PR candidate URL for {repo_id}")
        merge_oid = merge_commit.get("oid") or current.commit
        if merge_oid:
            merge_oid = _optional_sha(merge_oid, f"merge commit for {repo_id}")
        tracked = TargetTracking(
            status=status,
            pr=pr_url,
            commit=merge_oid,
            notes=current.notes,
            validation=current.validation,
            validation_urls=current.validation_urls,
            branch=head_branch,
            base_branch=base_branch,
            pr_head=current.pr_head,
            required_validation=current.required_validation,
            variants=current.variants,
            findings=current.findings,
        )
        updated[repo_id] = tracked
        if raw is not None:
            raw["tracking"][repo_id].update(
                {
                    "status": tracked.status,
                    "pr": tracked.pr,
                    "commit": tracked.commit,
                    "base_branch": tracked.base_branch,
                    "branch": tracked.branch,
                }
            )
    if raw is not None:
        _write_json_atomic(entry.path, raw)
    return updated


def _campaign_files(root: Path, patterns: Sequence[str]) -> tuple[Path, ...]:
    resolved_root = root.resolve()
    matches: set[Path] = set()
    for pattern in patterns:
        if Path(pattern).is_absolute() or ".." in PurePosixPath(pattern.replace("\\", "/")).parts:
            raise FleetError(f"unsafe campaign glob: {pattern!r}")
        for candidate in root.glob(pattern):
            if not candidate.is_file():
                continue
            resolved = candidate.resolve()
            if not resolved.is_relative_to(resolved_root):
                raise FleetError(f"campaign glob resolves outside repository: {candidate}")
            if resolved.stat().st_size > MAX_TEXT_FILE_SIZE:
                raise FleetError(f"campaign target is larger than 2 MiB: {candidate}")
            matches.add(resolved)
    return tuple(sorted(matches, key=lambda item: item.as_posix()))


def _read_text_bytes(path: Path) -> str:
    data = path.read_bytes()
    if b"\0" in data:
        raise FleetError(f"campaign target is not a text file: {path}")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise FleetError(f"campaign target is not UTF-8: {path}") from exc


def _regex_flags(names: Sequence[str]) -> int:
    result = 0
    for name in names:
        result |= getattr(re, name)
    return result


def plan_campaign(
    manifest: Manifest,
    workspace: Path,
    campaign: Campaign,
    repository_ids: Sequence[str] | None = None,
    *,
    allow_checkout_mismatch: bool = False,
    allow_default_branch: bool = False,
) -> CampaignPlan:
    selected = tuple(repository_ids or campaign.repositories)
    unknown = set(selected).difference(campaign.repositories)
    if unknown:
        raise FleetError(
            f"repository filter is outside this campaign: {', '.join(sorted(unknown))}"
        )
    if not selected:
        raise FleetError("campaign repository filter selected no repositories")

    roots: dict[str, Path] = {}
    checkout_heads: dict[str, str] = {}
    for repo_id in selected:
        repo = manifest.repositories[repo_id]
        root = repository_path(workspace, repo)
        if not root.is_dir():
            raise FleetError(f"campaign checkout is missing for {repo_id}: {root}")
        _verify_checkout_contract(
            repo,
            root,
            allow_checkout_mismatch=allow_checkout_mismatch,
            allow_default_branch=allow_default_branch,
        )
        head = _run_git(root, "rev-parse", "HEAD", check=False)
        if head.returncode != 0 or not head.stdout.strip():
            raise FleetError(f"campaign checkout has no committed HEAD for {repo_id}: {root}")
        roots[repo_id] = root
        checkout_heads[repo_id] = head.stdout.strip()

    current: dict[tuple[str, Path], str] = {}
    original: dict[tuple[str, Path], str] = {}
    file_steps: dict[tuple[str, Path], list[str]] = {}
    results: list[StepResult] = []

    for step in campaign.steps:
        for repo_id in step.repositories:
            if repo_id not in selected:
                continue
            root = roots[repo_id]
            files = _campaign_files(root, step.paths)
            if not files:
                raise FleetError(
                    f"campaign {campaign.id}/{step.id} matched no files in repository {repo_id}"
                )
            pending = 0
            already = 0
            regex = None
            already_regex = None
            if step.operation == "regex_replace":
                try:
                    regex = re.compile(step.find, _regex_flags(step.flags))
                    already_regex = re.compile(step.already_pattern or "", _regex_flags(step.flags))
                except re.error as exc:
                    raise FleetError(f"invalid regex in step {step.id!r}: {exc}") from exc

            for path in files:
                key = (repo_id, path)
                text = current.get(key)
                if text is None:
                    text = _read_text_bytes(path)
                    original[key] = text
                if step.operation == "literal_replace":
                    old_count = text.count(step.find)
                    new_count = text.count(step.replace) if step.replace else 0
                    changed = text.replace(step.find, step.replace)
                else:
                    assert regex is not None and already_regex is not None
                    old_count = len(tuple(regex.finditer(text)))
                    new_count = len(tuple(already_regex.finditer(text)))
                    changed, replaced = regex.subn(step.replace, text)
                    if replaced != old_count:
                        raise FleetError(f"internal regex count mismatch in step {step.id!r}")
                pending += old_count
                already += new_count
                current[key] = changed
                if changed != text:
                    file_steps.setdefault(key, []).append(step.id)

            expectation = step.expect[repo_id]
            observed = pending + already
            if not expectation.accepts(observed):
                raise FleetError(
                    f"campaign {campaign.id}/{step.id} expected {expectation.describe()} "
                    f"old-or-new occurrence(s) in {repo_id}, found {observed} "
                    f"({pending} pending, {already} already applied)"
                )
            results.append(
                StepResult(
                    step=step.id,
                    repository=repo_id,
                    files=len(files),
                    pending=pending,
                    already=already,
                    expected=expectation,
                )
            )

    changes: list[FileChange] = []
    for key, after in current.items():
        before = original[key]
        if before == after:
            continue
        repo_id, path = key
        changes.append(
            FileChange(
                repository=repo_id,
                path=path,
                relative_path=path.relative_to(roots[repo_id]).as_posix(),
                before=before,
                after=after,
                steps=file_steps.get(key, []),
            )
        )
    changes.sort(key=lambda change: (change.repository, change.relative_path))
    return CampaignPlan(
        campaign=campaign,
        selected_repositories=selected,
        results=tuple(results),
        changes=tuple(changes),
        checkout_heads=checkout_heads,
    )


def apply_campaign(
    manifest: Manifest,
    workspace: Path,
    plan: CampaignPlan,
    *,
    allow_dirty: bool = False,
    allow_checkout_mismatch: bool = False,
    allow_default_branch: bool = False,
) -> None:
    changed_repositories = sorted(set(plan.selected_repositories))
    for repo_id in changed_repositories:
        repo = manifest.repositories[repo_id]
        root = repository_path(workspace, repo)
        _verify_checkout_contract(
            repo,
            root,
            allow_checkout_mismatch=allow_checkout_mismatch,
            allow_default_branch=allow_default_branch,
        )
        head = _run_git(root, "rev-parse", "HEAD").stdout.strip()
        if head != plan.checkout_heads.get(repo_id):
            raise FleetError(
                f"checkout changed after planning for {repo_id}: "
                f"expected {plan.checkout_heads.get(repo_id)}, found {head}"
            )
    for change in plan.changes:
        if _read_text_bytes(change.path) != change.before:
            raise FleetError(
                f"campaign target changed after planning: "
                f"{change.repository}/{change.relative_path}"
            )
    if not plan.changes:
        return
    if not allow_dirty:
        dirty = []
        for repo_id in changed_repositories:
            root = repository_path(workspace, manifest.repositories[repo_id])
            _, state = git_status(root)
            if state != "clean":
                dirty.append(repo_id)
        if dirty:
            raise FleetError(
                "refusing to apply to dirty repositories: "
                + ", ".join(dirty)
                + "; use fresh clones or pass --allow-dirty explicitly"
            )

    prepared: list[tuple[FileChange, Path, Path]] = []
    replaced: list[tuple[FileChange, Path]] = []
    try:
        for change in plan.changes:
            mode = stat.S_IMODE(change.path.stat().st_mode)
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{change.path.name}.", suffix=".fleet-tmp", dir=change.path.parent
            )
            temporary = Path(temporary_name)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(change.after.encode("utf-8"))
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, mode)
            backup_descriptor, backup_name = tempfile.mkstemp(
                prefix=f".{change.path.name}.", suffix=".fleet-backup", dir=change.path.parent
            )
            backup = Path(backup_name)
            with os.fdopen(backup_descriptor, "wb") as handle:
                handle.write(change.before.encode("utf-8"))
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(backup, mode)
            prepared.append((change, temporary, backup))
        for change, temporary, backup in prepared:
            os.replace(temporary, change.path)
            replaced.append((change, backup))
    except BaseException as exc:
        rollback_failures: list[str] = []
        for change, backup in reversed(replaced):
            try:
                os.replace(backup, change.path)
            except BaseException as rollback_exc:  # noqa: BLE001 - report every rollback failure
                rollback_failures.append(
                    f"{change.repository}/{change.relative_path}: {rollback_exc}"
                )
        if rollback_failures:
            raise FleetError(
                f"campaign apply failed ({exc}); rollback also failed for: "
                + "; ".join(rollback_failures)
            ) from exc
        raise FleetError(f"campaign apply failed and was rolled back: {exc}") from exc
    finally:
        for _, temporary, backup in prepared:
            for artifact in (temporary, backup):
                if artifact.exists():
                    artifact.unlink()


def campaign_diff(plan: CampaignPlan) -> str:
    chunks: list[str] = []
    for change in plan.changes:
        label = f"{change.repository}/{change.relative_path}"
        chunks.extend(
            difflib.unified_diff(
                change.before.splitlines(keepends=True),
                change.after.splitlines(keepends=True),
                fromfile=f"a/{label}",
                tofile=f"b/{label}",
            )
        )
    return "".join(chunks)


def campaign_matrix(
    manifest: Manifest,
    campaign: Campaign,
    repository_ids: Sequence[str] | None = None,
    *,
    ci_only: bool = False,
) -> dict[str, list[dict[str, str]]]:
    selected_ids = tuple(repository_ids or campaign.repositories)
    unknown = set(selected_ids).difference(campaign.repositories)
    if unknown:
        raise FleetError(
            f"repository filter is outside this campaign: {', '.join(sorted(unknown))}"
        )
    include: list[dict[str, str]] = []
    for repo_id in selected_ids:
        repo = manifest.repositories[repo_id]
        if ci_only and not repo.ci:
            continue
        if not repo.rollout_enabled:
            continue
        if repo.github is None:
            raise FleetError(f"campaign repository {repo_id!r} has no GitHub remote")
        include.append(
            {
                "id": repo.id,
                "github": repo.github,
                "checkout": repo.checkout,
                "default_branch": repo.default_branch,
                "maintenance_branch": repo.maintenance_branch,
            }
        )
    if not include:
        raise FleetError("campaign contains no repositories eligible for rollout")
    return {"include": include}


def json_compact(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)

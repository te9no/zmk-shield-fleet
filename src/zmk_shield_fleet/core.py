from __future__ import annotations

import difflib
import fnmatch
import hashlib
import json
import os
import re
import stat
import subprocess
import tempfile
import tomllib
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence


ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
GITHUB_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
MAX_TEXT_FILE_SIZE = 2 * 1024 * 1024


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
class Manifest:
    path: Path
    owner: str
    default_workspace: Path
    repositories: Mapping[str, RepositorySpec]
    mirrors: tuple[MirrorSpec, ...]


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


@dataclass(frozen=True)
class LedgerEntry:
    campaign: Campaign
    source: ChangeSource
    trigger: ChangeTrigger | None
    scope_module: str | None
    scope_all: bool
    tracking: Mapping[str, TargetTracking]

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


def _require_mapping(value: Any, context: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise FleetError(f"{context} must be an object/table")
    return value


def _require_string(value: Any, context: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value):
        raise FleetError(f"{context} must be a non-empty string")
    return value


def _optional_string(value: Any, context: str) -> str | None:
    if value is None:
        return None
    return _require_string(value, context)


def _string_tuple(value: Any, context: str, *, nonempty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise FleetError(f"{context} must be an array of non-empty strings")
    if nonempty and not value:
        raise FleetError(f"{context} must not be empty")
    return tuple(value)


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

    if raw.get("schema") != 1:
        raise FleetError("fleet manifest schema must be 1")
    fleet = _require_mapping(raw.get("fleet"), "fleet")
    owner = _require_string(fleet.get("owner"), "fleet.owner")
    workspace_value = _require_string(fleet.get("workspace", ".."), "fleet.workspace")
    default_workspace = (manifest_path.parent / workspace_value).resolve()

    repositories: dict[str, RepositorySpec] = {}
    raw_repositories = raw.get("repositories")
    if not isinstance(raw_repositories, list) or not raw_repositories:
        raise FleetError("repositories must be a non-empty array of tables")

    for index, item in enumerate(raw_repositories):
        table = _require_mapping(item, f"repositories[{index}]")
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
        ci = table.get("ci", True)
        if not isinstance(ci, bool):
            raise FleetError(f"repositories[{index}].ci must be a boolean")
        if ci and github is None:
            raise FleetError(f"repository {repo_id!r} is enabled for CI but has no github value")
        rollout_order = table.get("rollout_order")
        if rollout_order is not None and (
            not isinstance(rollout_order, int)
            or isinstance(rollout_order, bool)
            or rollout_order < 1
        ):
            raise FleetError(f"repositories[{index}].rollout_order must be a positive integer")

        repositories[repo_id] = RepositorySpec(
            id=repo_id,
            checkout=checkout,
            default_branch=_require_string(
                table.get("default_branch"), f"repositories[{index}].default_branch"
            ),
            maintenance_branch=_require_string(
                table.get("maintenance_branch", table.get("default_branch")),
                f"repositories[{index}].maintenance_branch",
            ),
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
        )

    mirrors: list[MirrorSpec] = []
    seen_mirrors: set[str] = set()
    for index, item in enumerate(raw.get("mirrors", [])):
        table = _require_mapping(item, f"mirrors[{index}]")
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
        result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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


def load_ledger_entry(
    manifest: Manifest, source: str | Path, *, allow_disabled: bool = True
) -> LedgerEntry:
    campaign = load_campaign(manifest, source, allow_disabled=allow_disabled)
    try:
        raw = json.loads(campaign.path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:  # load_campaign normally catches these
        raise FleetError(f"cannot read ledger entry {campaign.path}: {exc}") from exc
    table = _require_mapping(raw, "change")
    source_table = _require_mapping(table.get("source"), "change.source")
    source_info = ChangeSource(
        repository=_require_string(source_table.get("repository"), "change.source.repository"),
        from_revision=_optional_string(
            source_table.get("from_revision"), "change.source.from_revision"
        ),
        to_revision=_require_string(source_table.get("to_revision"), "change.source.to_revision"),
        change_url=_optional_string(source_table.get("change_url"), "change.source.change_url"),
        notes=_require_string(
            source_table.get("notes", ""), "change.source.notes", allow_empty=True
        ),
    )
    trigger_info = None
    if table.get("trigger") is not None:
        trigger_table = _require_mapping(table.get("trigger"), "change.trigger")
        trigger_info = ChangeTrigger(
            repository=_require_string(
                trigger_table.get("repository"), "change.trigger.repository"
            ),
            revision=_require_string(trigger_table.get("revision"), "change.trigger.revision"),
            change_url=_require_string(
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
        target = _require_mapping(tracking_table[repo_id], f"change.tracking.{repo_id}")
        status = _require_string(target.get("status"), f"change.tracking.{repo_id}.status")
        if status not in LEDGER_STATUSES:
            raise FleetError(
                f"change.tracking.{repo_id}.status must be one of: "
                + ", ".join(sorted(LEDGER_STATUSES))
            )
        tracking[repo_id] = TargetTracking(
            status=status,
            pr=_optional_string(target.get("pr"), f"change.tracking.{repo_id}.pr"),
            commit=_optional_string(target.get("commit"), f"change.tracking.{repo_id}.commit"),
            notes=_require_string(
                target.get("notes", ""), f"change.tracking.{repo_id}.notes", allow_empty=True
            ),
        )
    return LedgerEntry(
        campaign=campaign,
        source=source_info,
        trigger=trigger_info,
        scope_module=scope_module,
        scope_all=scope_all,
        tracking=tracking,
    )


def list_ledger_entries(manifest: Manifest) -> tuple[LedgerEntry, ...]:
    directory = manifest.path.parent / "changes"
    if not directory.exists():
        return ()
    return tuple(load_ledger_entry(manifest, path) for path in sorted(directory.glob("*.json")))


def mark_ledger_target(
    entry: LedgerEntry,
    repository: str,
    status: str,
    *,
    pr: str | None = None,
    commit: str | None = None,
    notes: str | None = None,
) -> None:
    if repository not in entry.tracking:
        raise FleetError(f"repository {repository!r} is not tracked by change {entry.campaign.id!r}")
    if status not in LEDGER_STATUSES:
        raise FleetError(f"invalid ledger status: {status!r}")
    raw = json.loads(entry.path.read_text(encoding="utf-8"))
    target = raw["tracking"][repository]
    target["status"] = status
    if pr is not None:
        target["pr"] = pr or None
    if commit is not None:
        target["commit"] = commit or None
    if notes is not None:
        target["notes"] = notes
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


def github_pull_requests(repository: str, branch: str) -> list[dict[str, Any]]:
    command = [
        "gh", "pr", "list", "--repo", repository, "--head", branch, "--state", "all",
        "--limit", "20", "--json",
        "number,url,state,isDraft,mergedAt,mergeCommit,createdAt,updatedAt",
    ]
    try:
        result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError as exc:
        raise FleetError("gh is required for ledger sync") from exc
    if result.returncode != 0:
        raise FleetError(f"cannot query {repository}: {result.stderr.strip()}")
    return json.loads(result.stdout)


def sync_ledger_entry(
    manifest: Manifest,
    entry: LedgerEntry,
    *,
    write: bool = False,
    fetcher=github_pull_requests,
) -> Mapping[str, TargetTracking]:
    updated = dict(entry.tracking)
    raw = json.loads(entry.path.read_text(encoding="utf-8")) if write else None
    branch = f"fleet/{entry.campaign.id}"
    for repo_id, current in entry.tracking.items():
        if current.status == "not-applicable":
            continue
        spec = manifest.repositories[repo_id]
        if spec.github is None:
            continue
        pulls = fetcher(spec.github, branch)
        if not pulls:
            continue
        pull = max(pulls, key=lambda item: item.get("updatedAt") or item.get("createdAt") or "")
        if pull.get("mergedAt"):
            status = "merged"
        elif pull.get("state") == "OPEN":
            status = "pr-open"
        else:
            status = "closed"
        merge_commit = pull.get("mergeCommit") or {}
        tracked = TargetTracking(
            status=status,
            pr=pull.get("url") or current.pr,
            commit=merge_commit.get("oid") or current.commit,
            notes=current.notes,
        )
        updated[repo_id] = tracked
        if raw is not None:
            raw["tracking"][repo_id].update(
                {"status": tracked.status, "pr": tracked.pr, "commit": tracked.commit}
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
    for repo_id in selected:
        repo = manifest.repositories[repo_id]
        root = repository_path(workspace, repo)
        if not root.is_dir():
            raise FleetError(f"campaign checkout is missing for {repo_id}: {root}")
        is_git, _ = git_status(root)
        if not is_git:
            raise FleetError(f"campaign checkout is not a Git repository for {repo_id}: {root}")
        roots[repo_id] = root

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
    )


def apply_campaign(
    manifest: Manifest,
    workspace: Path,
    plan: CampaignPlan,
    *,
    allow_dirty: bool = False,
) -> None:
    if not plan.changes:
        return
    changed_repositories = sorted({change.repository for change in plan.changes})
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

    prepared: list[tuple[FileChange, Path]] = []
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
            prepared.append((change, temporary))
        for change, temporary in prepared:
            os.replace(temporary, change.path)
    finally:
        for _, temporary in prepared:
            if temporary.exists():
                temporary.unlink()


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

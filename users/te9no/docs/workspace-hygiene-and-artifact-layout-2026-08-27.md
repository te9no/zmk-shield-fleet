# Workspace hygiene and firmware artifact layout

Date: 2026-08-27; updated 2026-08-28

This is the Fleet record of a local workspace cleanup. It records placement,
recovery, deletion, and retained-storage decisions without treating filesystem
maintenance as a firmware rollout or pull-request authorization.

## Owner-approved cleanup 2026-08-28

This update supersedes the historical retention/approval snapshot below. The
owner separately approved removal of the old SAA checkout, unused worktrees,
and the approximately 45 GiB legacy archive. Those operations are complete;
they do not authorize further deletions.

- Removed four unused worktrees and their individual registrations: archived
  `saa-three-wire-spi-module`, `work/saa-pmw-validation`,
  `work/fleet-audit-request-ui`, and `work/record-polaris-pmw-applied`.
  Their allocated size was 275,288,064 bytes (about 262.5 MiB). Branch history
  and administrative metadata were retained; additional recovery refs protect
  the three `work/` entries. No meaningful uncommitted source was lost.
- Removed the exact `.zmk-workspace/archive/20260827-083105` after checking
  that current profiles and live Git references did not depend on it. After
  the separate archived-SAA removal, its remaining allocated size was
  48,420,225,024 bytes (about 45.1 GiB). The original directory no longer exists.
- Preserved Git history/metadata, dirty and untracked source, broken snapshots,
  temporary tools, logs, and generated DTS/config/build provenance in
  `.zmk-workspace/archive/20260828-legacy-recovery/`. Full content verification
  covered 45,945 files and 19,285 unique contents, including three dirty module
  repositories and two broken historical snapshots. Local `files.json`,
  `repositories.json`, and `VERIFIED.json` record the checks; private manifests
  and raw recovery data are not published to Fleet.
- The recovery tarball is 3,098,363,190 bytes; its directory occupies
  3,108,462,592 allocated bytes (about 2.9 GiB). Net archive space recovered is
  about **42.2 GiB**, separate from the earlier four-worktree cleanup.
  Source/history/evidence can be recovered from the package; discarded build
  caches must be regenerated. The Windows-host WSL virtual disk was not compacted.
- Post-cleanup checks passed: 18 workspace-path regression tests, all eight
  profile source locations, active Git worktree references with no prunable
  registrations, and the read-only Madula IQS artifact/CDC resolver. Current
  firmware was preserved, including `firmware/zmk-keyboard-cornix/main/madula_iqs.uf2`
  with SHA-256 `6191ba66643c7272768436b94a8df48dee56494a0342a0157823ebb2e9c3d926`.
  Workspace `main@14838370` remains clean. No build, flash, or hardware test was
  performed by this cleanup.

All eight profiles, their referenced checkouts (including retired ESB), the
external Polaris worktree, ccache, old firmware archive, and separate Fleet-source
archive remain. Their older sizes below are historical, not fresh measurements.
Additional cleanup requires its own scope/retention decision and approval. The
completed archive operation is removed from the pending work queue.

## Initial cleanup (historical snapshot)

- `firmware/` now uses canonical repository and branch destinations. It was
  reduced from 442 files / 323 MiB to 64 files / 49.8 MiB. The old aggregate
  was moved to a recoverable archive before the canonical set was selected.
- Approximately 11 GiB of obsolete build profiles was deleted only after owner
  approval. This deletion is distinct from archive-first repository handling.
- Git repositories and worktrees were removed from both the workspace-root and
  Fleet-nested `.fleet-workspace` directories. The empty directories were then
  removed.
- The 77 discovered entries were classified as 29 active entries under `work/`
  and 48 archive entries. Ten broken worktree pointers were preserved in the
  inventory instead of being silently discarded. The later re-audit below
  supersedes the original claim that all active Git references were repaired.
- Active Polaris, Fleet, and SAA repository/worktree references were repaired.

## Placement contract

| Location | Purpose |
| --- | --- |
| `config/` | Canonical repository checkouts |
| `work/` | Temporary clones and Git worktrees |
| `.fleet-workspace/` | No Git repositories or worktrees are permitted |
| `firmware/<repository>/<branch>/` | Canonical generated firmware destination |

Future cleanup must inventory entries before moving them. Broken pointers are
evidence, not permission to delete an archive. Recursive deletion remains an
explicitly approved operation.

## Workspace source state

The workspace changes are published through
[`main@14838370`](https://github.com/te9no/zmk-workspace/commit/148383705c155920be46a48a79d6c6e26127b879):

- `4a979e52` — profile and firmware artifact handling;
- `9b461ad5` — CDC bootloader disconnect handling during serial open;
- `9e10e81f` — repository placement documentation;
- `97420d11` — local Visual Studio workspace data exclusion;
- `7e19e13c` — reusable badge workflow validation repair.
- `14838370` — current-checkout artifact resolution, shared CDC resolution,
  profile-local CDC logs, read-only path checks, and 18 regression tests.

The reusable workflow now has a valid GitHub-recognized workflow name and input
description. The malformed workflow no longer creates an invalid push run.
Local `main` and remote `te9no/main` both resolve to `14838370`.

Workspace maintenance is performed directly on `main`; it does not use a
feature branch or PR. This record documents the completed publication and does
not authorize unrelated workspace changes.

## Re-audit and fixes (2026-08-27 historical snapshot)

The owner authorized implementation after the read-only audit. No keyboard
firmware source, hardware validation result, or device was changed by this
workspace maintenance.

### Artifact and CDC resolution

The old wrapper treated saved metadata as a branch pin. Madula's checkout had
already moved to `main`, and MKB's three-wire checkout was on
`codex/mkb-via-support`, but paths still used their old branch names. The CDC
helper independently inspected legacy root west directories, which no longer
existed, and could fall back to another branch's unique matching UF2.

- Resolution is now explicit environment override, live checkout `origin` name
  and branch, last-known metadata, then profile name. Detached checkouts use
  `detached-<12-character SHA>`. Path queries never rewrite metadata.
- `paths`, Docker build environment, and CDC helper agree on the destination.
  `firmware-dir` and `log-dir` provide machine-readable paths without Docker.
- `flash-log --resolve <artifact>` checks an existing UF2 without building,
  flashing, opening serial ports, or making log directories. Cross-branch
  automatic fallback was removed; explicit UF2 paths remain supported.
- Default CDC logs now stay under the selected profile's `logs/zmk/`.
- Both Bash syntax checks and all **18 isolated regression tests** passed
  locally and in [Workspace path tests CI](https://github.com/te9no/zmk-workspace/actions/runs/33083235604).
  Tests cover branch switches, detached HEAD, metadata fallback, moved checkout,
  explicit overrides, Docker environment forwarding, and CDC path safety.
- Live read-only checks covered all eight profiles. Madula now resolves to
  `firmware/zmk-keyboard-cornix/main/`, MKB three-wire to
  `firmware/zmk-config-MKB2/codex-mkb-via-support/`. Resolving the existing
  `madula_trackpoint.uf2` through the profile wrapper succeeded.
- **No firmware build or flash was performed** for this path-only maintenance.

### Git references and preservation

- The absent `config/zmk-config-MKB2-main` registration was retired, not broadly
  pruned. Its detached HEAD `0b74cb752caa45cd127c9adce01012a915c94133` is protected
  by local `refs/recovery/workspace-20260827/mkb-main`, and its entire admin
  directory/index/reflog was backed up and moved into the re-audit archive.
- SAA's apparently missing worktree was found under
  `.zmk-workspace/archive/20260827-083105/.tmp/worktrees/saa-three-wire-spi-module`.
  Both Git pointers were repaired to the archive, and the worktree was locked
  for retention. Its branch/HEAD and existing line-ending differences remain
  untouched. It must not be deleted as disposable build cache.
- Fleet `work/fleet-audit-request-ui` existed: its Windows UNC back-pointer was
  repaired to the Linux path. Source content and HEAD were preserved.
- The external Polaris worktree under the workspace parent's `worktrees/`
  exists on the host. The final Linux audit mounted it read-only; it was not
  falsely pruned due to an incomplete container mount.
- Enumerating active repositories under `config/*`, `work/*`, and nested
  `work/fresh-audit-*/*` found no broken repository or prunable worktree after
  repair. Historical broken snapshots in the old Fleet archive remain outside
  this active-repository result and are still preserved.
- Recovery details are in local
  `.zmk-workspace/archive/20260827-workspace-reaudit/INVENTORY.md`, along with
  before-repair metadata. No blanket prune, reset, or source deletion was used.
- `organize --dry-run` reports no legacy root directories. Neither root nor
  canonical Fleet `.fleet-workspace/` exists.

## Retained storage before approved deletion (historical snapshot)

The previous 6.9 / 3.8 / 2.2 GiB summary was incomplete and is superseded here.
All entries below were retained at the 2026-08-27 re-audit. The legacy archive
was subsequently removed as recorded above. Sizes are allocated bytes measured
with `du -B1 -s`; new builds can change them.

| Location under `.zmk-workspace/` | Bytes | Reason / next decision |
| --- | ---: | --- |
| `profiles/madula-lpps-validation` | 3443777536 | Accepted LPPS build and logs |
| `profiles/mkb-three-wire-module` | 3893530624 | Current MKB development and regression artifacts |
| `profiles/mkb-xiao-pinmux` | 5135646720 | XIAO rollout evidence; compare before deduplicating |
| `profiles/polaris-esb-validation` | 3963326464 | Retired experiment; cleanup candidate, owner approval pending |
| `profiles/polaris-three-wire-module` | 3465506816 | Accepted three-wire baseline and evidence |
| `profiles/polaris-xiao-pin-release` | 4223090688 | XIAO rollout baseline and evidence |
| `profiles/saa-xiao-pinmux` | 5497315328 | Dedicated branch; hardware validation still pending |
| `profiles/solstice-xiao-pinmux` | 3779039232 | Solstice rollout baseline and evidence |
| `cache/ccache` | 4019814400 | Rebuild acceleration; reproducible, retained for now |
| `archive/20260827-083105` | 48554426368 | Legacy builds/west **and source worktrees**; classify before deletion |
| `archive/20260827-090311-firmware-layout` | 339955712 | Previous aggregate firmware recovery baseline |
| `archive/20260827-094045-fleet-workspace` | 2273910784 | Source snapshots, dirty files, historical broken pointers |

Totals: eight profiles **31.11 GiB**; shared ccache **3.74 GiB**; legacy
build/west archive **45.22 GiB**; previous firmware **324.21 MiB**; archived
Fleet sources **2.12 GiB**. The new Git metadata backup was 216 KiB before
its inventory text was added.

Current `firmware/` contains **118 files / 97,941,504 logical bytes (93.40 MiB)**,
or 98,242,560 allocated bytes. All files are under repository/branch directories;
growth since the initial 64-file cleanup is recorded, not treated as a failed
cleanup or silently removed.

At that re-audit, the retained-storage review was complete but deletion approval
was still pending, separately from the completed path/Git repairs. The later
owner-approved cleanup above supplied that approval, separated and verified
source/history/evidence, and removed the legacy archive. This historical table
is not a current deletion queue. Further cleanup still requires fresh inspection
and explicit approval for its own targets.

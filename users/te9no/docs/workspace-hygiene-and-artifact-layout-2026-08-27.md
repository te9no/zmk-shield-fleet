# Workspace hygiene and firmware artifact layout

Date: 2026-08-27

This is the Fleet record of a local workspace cleanup. It records placement,
recovery, deletion, and retained-storage decisions without treating filesystem
maintenance as a firmware rollout or pull-request authorization.

## Result

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
  inventory instead of being silently discarded. Git reports zero prunable
  worktrees after repair.
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
[`main@7e19e13c`](https://github.com/te9no/zmk-workspace/commit/7e19e13cd4bfee531318674b95014a391a1fedeb):

- `4a979e52` — profile and firmware artifact handling;
- `9b461ad5` — CDC bootloader disconnect handling during serial open;
- `9e10e81f` — repository placement documentation;
- `97420d11` — local Visual Studio workspace data exclusion;
- `7e19e13c` — reusable badge workflow validation repair.

The reusable workflow now has a valid GitHub-recognized workflow name and input
description. The malformed workflow no longer creates an invalid push run.
Local `main` and `te9no/main` both resolve to `7e19e13c`.

Workspace maintenance is performed directly on `main`; it does not use a
feature branch or PR. This record documents the completed publication and does
not authorize unrelated workspace changes.

## Intentionally retained storage

- Current MKB and Polaris profiles: 6.9 GiB;
- shared ccache: 3.8 GiB;
- archived repository snapshots: 2.2 GiB.

These are retained deliberately for current validation, build acceleration, and
recovery. Any later deletion requires a fresh inventory and explicit approval.

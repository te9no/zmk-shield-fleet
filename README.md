# zmk-shield-fleet

`zmk-shield-fleet` tracks and propagates shared ZMK driver, module, shield, and
configuration changes across multiple keyboard repositories.

It is not a firmware dependency. Each keyboard keeps its own hardware-specific
configuration; this project provides inventory checks, a change ledger,
revision audits, guarded text migrations, and optional draft-PR rollout.

## What it solves

When one keyboard proves a shared fix, the fleet ledger records:

- the upstream driver or module revision;
- the reference keyboard commit that verified it;
- every repository that consumes the affected module;
- whether each target is pending, in a PR, merged, applied, blocked, or not applicable;
- optional deterministic edits for `west.yml`, overlays, `.conf` files, and other UTF-8 text files.

Module-scoped entries are checked against the inventory. Adding another consumer
without adding it to an open ledger entry makes validation fail, preventing a
keyboard from silently being omitted.

## Install

Python 3.11 or newer is required. There are no runtime Python dependencies.

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
```

## Create a profile

Copy the templates into a user profile:

```text
users/alice/
├── fleet.toml       # based on examples/fleet.toml
└── changes/
    └── driver-fix.json
```

Personal inventories belong in `users/<name>/`; the CLI and schema remain
generic. See [`users/README.md`](users/README.md) and
[`examples/change.json.disabled`](examples/change.json.disabled).

## Typical workflow

```sh
MANIFEST=users/alice/fleet.toml

shield-fleet inventory --manifest "$MANIFEST"
shield-fleet audit --manifest "$MANIFEST"
shield-fleet ledger check --manifest "$MANIFEST"
shield-fleet ledger list --manifest "$MANIFEST"
```

For a deterministic migration, review the complete diff before writing:

```sh
shield-fleet change plan driver-fix --manifest "$MANIFEST" --diff
shield-fleet change apply driver-fix --manifest "$MANIFEST" --diff
```

Record-only entries may use `"steps": []`. They still act as complete,
scope-checked propagation checklists, but cannot be sent to automated rollout
until guarded steps are added.

## Revision pinning

Moving west revisions such as `main`, `master`, and branch names make builds
non-reproducible. Find them, plus abbreviated SHAs, with:

```sh
shield-fleet revisions --manifest "$MANIFEST"
shield-fleet revisions --manifest "$MANIFEST" --strict-sha
```

Use `--check` in CI after the fleet has been fully pinned.

## Draft pull-request rollout

The `Roll out driver change` workflow accepts a profile manifest and change ID,
then creates `fleet/<change-id>` draft PRs in eligible repositories. Configure a
fine-grained `FLEET_TOKEN` secret with Contents and Pull requests read/write
access only to the target repositories.

After PRs are merged, synchronize their state back into the ledger:

```sh
shield-fleet ledger sync driver-fix --manifest "$MANIFEST" --write
```

## Safety model

- all repositories and target files are explicit;
- replacement counts are validated before any file is written;
- every selected repository is preflighted before apply;
- dirty worktrees are rejected unless `--allow-dirty` is explicitly supplied;
- migrations cannot run arbitrary shell commands or create/delete files;
- rollout PRs are drafts by default.

## Development

```sh
python -m unittest discover -s tests -v
shield-fleet ledger check --manifest users/te9no/fleet.toml
```

The legacy `campaign` command remains as a compatibility alias for `change`.

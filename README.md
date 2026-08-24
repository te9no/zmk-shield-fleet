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
- optional CI and hardware validation gates, tracked independently from whether code is already `applied`;
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

Fork this repository, then copy the templates into a user profile:

```text
users/alice/
├── fleet.toml       # based on examples/fleet.toml
└── changes/
    └── driver-fix.json
```

Personal inventories belong in `users/<name>/`; the CLI and schema remain
generic. See [`users/README.md`](users/README.md) and
[`examples/change.json.disabled`](examples/change.json.disabled).

The shortest end-to-end setup is:

```sh
mkdir -p users/alice/changes
cp examples/fleet.toml users/alice/fleet.toml
cp examples/change.json.disabled users/alice/changes/driver-fix.json

shield-fleet ledger check --manifest users/alice/fleet.toml
shield-fleet audit --manifest users/alice/fleet.toml
python3 scripts/build_dashboard.py
python3 -m http.server 8000 --directory site
```

Edit the copied owner, workspace, repository, scope, and evidence values before
committing. Open <http://127.0.0.1:8000/#next-actions> to review the result, then
enable GitHub Pages with **GitHub Actions** as its source. The included Pages
workflow validates every enabled ledger before publishing it.

Profiles may also declare a curated, ordered work queue. This metadata is
optional and stays in the profile rather than dashboard JavaScript:

```toml
[[next_actions]]
id = "verify-keyboard-a"
state = "active"       # active, waiting, or later
priority = "high"      # high, medium, or low
order = 1
repository = "keyboard-a"
action = "Flash the validation firmware and test pointer input."
completion = "Pointer input and bootloader recovery pass on hardware."
blocker = ""
pr = "https://github.com/example/zmk-config-keyboard-a/pull/12"
change_id = "driver-fix"
validation_keys = ["ci", "hardware"]
variant_ids = ["keyboard-a-left", "keyboard-a-right"]
evidence = [
  { label = "Hardware checklist", status = "passed", url = "https://github.com/example/zmk-config-keyboard-a/blob/zmk-0.4/docs/validation.md" },
]
```

`repository` may name an inventory ID or an adjacent module repository. For an
adjacent repository, set `repository_url` so its card has a useful link. An
explicit `repository_url` also overrides the inventory anchor, which is useful
for a dedicated validation branch.

`change_id` links a card to a schema-validated ledger entry. Optional
`validation_keys` selects checks to show on the card, `variant_ids` names the
firmware variants covered by the action, and `evidence` adds adjacent evidence
that does not belong to a ledger check. Every evidence item has a short label,
`passed`, `pending`, `failed`, or `waived` status, and an HTTPS URL.

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

## Dashboard

The repository includes a reusable static dashboard in `site/`. GitHub Pages
builds its data from every committed `users/*/fleet.toml` profile and change
ledger after schema-validating every ledger, so invalid data cannot be published
by Pages and status updates appear without hand-editing HTML. The dashboard shows
fleet totals, profile-defined next actions, propagation progress, the
repository/change matrix, and revision pinning findings. Next-action cards can
be filtered by actionable work, hardware/external waits, and deferred or
out-of-scope work. The first currently actionable entry is also shown once as
**Start here**; this does not change the profile's explicit priority or order.
Validation checks are rendered individually, so each named evidence URL remains
reachable on desktop and mobile.

All committed `users/*/fleet.toml` profiles and their enabled change ledgers are
included in the public dashboard payload. Never commit credentials, private
clone URLs, private evidence URLs, local absolute paths, or firmware binaries.

Forks can configure public project metadata without editing dashboard JavaScript:

- `FLEET_PROJECT_NAME`: dashboard/project label;
- `FLEET_PROJECT_URL`: public source repository URL;
- `FLEET_SITE_URL`: deployed site root used by Open Graph metadata;
- `FLEET_LOCALE`: fallback BCP 47 locale;
- `FLEET_SOURCE_COMMIT`: source revision when Git metadata is unavailable.

GitHub Actions supplies the repository and commit automatically. A profile's
locale is inferred from its curated action text unless the typed manifest model
provides one explicitly.

`site/data.json` is a generated Pages/local-preview artifact. It is intentionally
untracked and listed in `.gitignore`, so its `generated_at` timestamp never
creates a source-tree diff or an automated commit. The Pages workflow generates
it after checkout and uploads the complete `site/` directory as its deployment
artifact.

Preview it locally after regenerating the data:

```sh
python3 scripts/build_dashboard.py
python3 -m http.server 8000 --directory site
```

Then open <http://127.0.0.1:8000/#next-actions>.
Regenerating the payload updates the ignored `site/data.json` file only; remove
it when finished if you do not want to retain the local preview artifact.

Dashboard model helpers also have dependency-free Node tests:

```sh
node --test site/model.test.mjs
node --check site/app.js
```

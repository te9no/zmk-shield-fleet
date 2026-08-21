# Driver-change ledger

Each `<id>.json` records one upstream driver/module change and its propagation
state in every consuming keyboard repository. A ledger entry may also contain
guarded replacement steps for `west.yml`, overlays, Kconfig `.conf` files, and
other UTF-8 text files.

`trigger` points to the keyboard commit that proved the change. `scope` may be
`{"module": "iqs9151"}` or `{"all": true}`. Ledger validation derives the
matching repositories from `fleet.toml` and fails if even one target is omitted.
`steps` may be empty for a record/checklist-only change.

Start from `../examples/change.json.disabled`, then record the upstream change,
list every target, describe deterministic replacements, and review
`shield-fleet change plan <id> --diff` before enabling it.

Use `shield-fleet ledger mark` for manual updates and `shield-fleet ledger sync
<id> --write` to discover PRs created from branch `fleet/<id>`.

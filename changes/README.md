# Driver-change ledger

Each `<id>.json` records one upstream driver/module change and its propagation
state in every consuming keyboard repository. A ledger entry may also contain
guarded replacement steps for `west.yml`, overlays, Kconfig `.conf` files, and
other UTF-8 text files.

`trigger` points to the keyboard commit that proved the change. `scope` may be
`{"module": "iqs9151"}` or `{"all": true}`. Ledger validation derives the
matching repositories from `fleet.toml` and fails if even one target is omitted.
`steps` may be empty for a record/checklist-only change.

Targets may declare named validation gates such as
`"validation": {"ci": "passed", "hardware": "pending"}`. Allowed values are
`pending`, `passed`, `failed`, and `waived`. Once gates are declared, every gate
must be `passed` or explicitly `waived` before the target can be marked
`applied`. A merged PR with pending validation remains visibly incomplete on the
dashboard.

`validation_urls` may attach an HTTPS evidence link to any declared check. The
dashboard makes both these links and the target PR directly clickable.

Start from `../examples/change.json.disabled`, then record the upstream change,
list every target, describe deterministic replacements, and review
`shield-fleet change plan <id> --diff` before enabling it.

Use `shield-fleet ledger mark` for manual updates and `shield-fleet ledger sync
<id> --write` to discover PRs created from branch `fleet/<id>`.

```sh
shield-fleet ledger mark driver-fix --repo keyboard-a --status pr-open \
  --validation-check ci=passed --validation-check hardware=pending \
  --validation-url ci=https://github.com/example/keyboard/actions/runs/123 \
  --validation-url hardware=https://github.com/example/keyboard/blob/fleet/driver-fix/docs/validation.md
```

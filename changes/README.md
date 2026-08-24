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
`pending`, `passed`, `failed`, and `waived`. `required_validation` can name the
gates that control completion; otherwise every declared gate controls it. A
target may be recorded as `applied` while hardware validation is still pending,
but it is not considered complete until required gates pass or are waived.
Terminal targets with no validation evidence are also incomplete. A
`not-applicable` target cannot declare validation because that is contradictory.

`validation_urls` may attach an HTTPS evidence link to any declared check. The
dashboard makes both these links and the target PR directly clickable.

Hardware variants use a typed list. Every listed variant participates in
completion and may contain gate-level validation and structured HTTPS evidence:

```json
"variants": [{
  "id": "left",
  "status": "pending",
  "validation": {"hardware": "pending"},
  "evidence": [{
    "label": "bench log",
    "status": "pending",
    "url": "https://github.com/example/keyboard/actions/runs/123"
  }]
}]
```

For deterministic PR discovery, target tracking may set `branch` (the PR head
branch), `base_branch`, and `pr_head` (the expected full 40-character head SHA).
Sync stops if multiple PRs match or the recorded SHA disagrees with GitHub.
Next actions may use `change_id`, `validation_keys`, and `variant_ids`; ledger
check verifies every reference. Their `evidence` field uses the same structured
evidence objects shown above.

Start from `../examples/change.json.disabled`, then record the upstream change,
list every target, describe deterministic replacements, and review
`shield-fleet change plan <id> --diff` before enabling it.

Use `shield-fleet ledger mark` for manual updates and `shield-fleet ledger sync
<id> --write` to discover PRs created from the target `branch` (or the fallback
`fleet/<id>`) into its `base_branch`.

Automated rollout is opt-in per repository with `rollout_enabled = true`. Such
repositories require an explicit maintenance branch different from the default
branch. External GitHub owners also require `allow_external = true`. Local
planning and applying verify origin, current maintenance branch, and the planned
HEAD; stable/default branch access requires `--allow-default-branch`, and origin
or branch exceptions require `--allow-checkout-mismatch`.

```sh
shield-fleet ledger mark driver-fix --repo keyboard-a --status pr-open \
  --validation-check ci=passed --validation-check hardware=pending \
  --validation-url ci=https://github.com/example/keyboard/actions/runs/123 \
  --validation-url hardware=https://github.com/example/keyboard/blob/fleet/driver-fix/docs/validation.md
```

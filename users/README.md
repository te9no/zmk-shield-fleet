# User profiles

Personal fleet inventories and change ledgers live under `users/<name>/` so the
root project remains reusable. A profile normally contains:

```text
users/<name>/
├── fleet.toml
├── changes/
└── docs/
```

Commands receive the profile manifest explicitly:

```sh
shield-fleet ledger list --manifest users/<name>/fleet.toml
shield-fleet audit --manifest users/<name>/fleet.toml
```

Do not commit credentials, private clone URLs containing tokens, firmware
binaries, or local absolute paths.

## Next actions

An optional `[[next_actions]]` array in `fleet.toml` drives the prominent work
queue on the public dashboard. Each entry records a stable ID, `active`,
`waiting`, or `later` state, `high`, `medium`, or `low` priority, numeric order,
repository label, concrete action, completion condition, blocker, and optional
PR/repository URLs. Keep personal prioritization in this profile metadata; do
not add profile-specific branching or repository names to `site/app.js`.

See [`../../examples/fleet.toml`](../../examples/fleet.toml) for a complete
example.

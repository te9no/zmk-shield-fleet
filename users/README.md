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

When an action corresponds to a change ledger, set `change_id` and optionally
`validation_keys` so the card exposes the named ledger checks and every matching
evidence URL. `variant_ids` narrows the task to explicit firmware variants.
Adjacent proof can be declared as typed `evidence` entries with `label`,
`status`, and HTTPS `url` fields. URL-only evidence lists remain displayable for
older profiles, but labeled objects are preferred because they preserve meaning.
The dashboard presents one actionable item as **Start here**, while preserving
the profile's numeric order and priority.

Everything committed below `users/` is included in the public Pages payload.
Do not record credentials, private evidence, private repository URLs, or local
absolute paths in profile metadata, notes, or ledgers.

See [`../../examples/fleet.toml`](../../examples/fleet.toml) for a complete
example.

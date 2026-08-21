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

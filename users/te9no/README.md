# te9no fleet profile

This directory contains te9no's personal ZMK repository inventory, propagation
ledger, and audit notes. It is data consumed by the generic `shield-fleet` CLI;
none of it is required by other users of the project.

```sh
shield-fleet ledger list --manifest users/te9no/fleet.toml
shield-fleet audit --manifest users/te9no/fleet.toml
shield-fleet revisions --manifest users/te9no/fleet.toml
```

# te9no fleet profile

This directory contains te9no's personal ZMK repository inventory, propagation
ledger, and audit notes. It is data consumed by the generic `shield-fleet` CLI;
none of it is required by other users of the project.

`rollout_order` is the personal deployment queue shown on GitHub Pages. MKB2 is
first, GeaconSolstice is second, and order 99 is the lowest-priority backlog.
CI success only advances a validation branch; default-branch promotion requires
hardware validation.

```sh
shield-fleet ledger list --manifest users/te9no/fleet.toml
shield-fleet audit --manifest users/te9no/fleet.toml
shield-fleet revisions --manifest users/te9no/fleet.toml
```

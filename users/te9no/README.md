# te9no fleet profile

This directory contains te9no's personal ZMK repository inventory, propagation
ledger, and audit notes. It is data consumed by the generic `shield-fleet` CLI;
none of it is required by other users of the project.

`rollout_order` is the personal deployment queue shown on GitHub Pages. Cornix
Madula Trackball is complete on `main@794987c`. Madula IQS input/direction and
its CDC boot/log path passed on 2026-08-28; the SDA/rotation fix is integrated in
`main@578c9f1`. IQS extended checks and Trackball's 1200-baud check remain
independent items. SAA is consolidated on the dedicated `zmk-0.4` branch and is the currently active hardware
validation; MKB2 and GeaconSolstice follow as already validated references, and
order 99 is the lowest-priority backlog.
CI success only advances a validation branch; default-branch promotion requires
hardware validation.

> **Public profile:** GitHub Pages publishes the profile data under this
> directory. Treat every repository name, note, branch, PR, commit, validation
> result, and evidence URL here as public. Never record secrets, tokens, private
> repository details, stable device identifiers, local paths, or raw logs
> containing personal information.

Fleet work is ledger-first. By default, an audit or hardware observation is
recorded as a pending ledger item only. Managed keyboard repositories and shared
modules are not modified unless te9no explicitly requests implementation of that
specific item.

Every managed repository currently declares `rollout_enabled = false` and
`allow_external = false`. These are deny-by-default gates: inventory and audit
do not authorize a firmware write, branch push, PR creation, PR comment, close,
or merge. External repositories always require a separate, explicit approval.
Recovery procedures are in [runbook/recovery.md](runbook/recovery.md).

```sh
shield-fleet ledger list --manifest users/te9no/fleet.toml
shield-fleet audit --manifest users/te9no/fleet.toml
shield-fleet revisions --manifest users/te9no/fleet.toml
```

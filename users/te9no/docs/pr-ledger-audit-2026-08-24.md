# PR and ledger audit — 2026-08-24

The authoritative inventory is `users/te9no/fleet.toml`. This refresh uses each
repository's maintenance branch as the operational baseline: Polaris, MKB2,
Cornix, and Solstice use `zmk-0.4`; SAA uses the isolated
`zmk-0.4_validation_cormoran-zmk`. Stable firmware `main`/`master` was not
changed. No external repository was changed.

## Current decisions

- Polaris [PR #7](https://github.com/te9no/zmk-config-GeaconPolaris/pull/7) remains Draft against `zmk-0.4`. Its right TB/TPD/IQS 9/9 CI and generated config/DTS checks passed; right-side flash, CDC Debug, and 1200-baud boot remain hardware pending. PR #6 is the separately merged Cormoran/Bongo baseline.
- Cornix [PR #3](https://github.com/te9no/zmk-keyboard-cornix/pull/3) remains the highest-priority Draft against `zmk-0.4`. Run [32627774654](https://github.com/te9no/zmk-keyboard-cornix/actions/runs/32627774654), firmware flash, CDC enumeration, and DYA Studio passed. A physical Madula trackball and the 1200-baud transition still need verification. PR #1 is already merged and is the authoritative DYA/IQS/west baseline.
- SAA's current source of truth is [the dedicated validation branch](https://github.com/te9no/zmk-config-SparAkashaAnanta/tree/zmk-0.4_validation_cormoran-zmk) at `4e54e1c51b1a161ffc1c174f72f9150ee31d6bb8`, not a PR. Run [32628652475](https://github.com/te9no/zmk-config-SparAkashaAnanta/actions/runs/32628652475) passed all 21 targets. Historical PRs #2/#3/#4 merged into the feature branch, but the attempted `master` promotion was reverted by PR #6; ledger status is therefore `applied`, never `merged` to stable `master`.
- MKB2's integrated source of truth is merged [PR #14](https://github.com/te9no/zmk-config-MKB2/pull/14), run [32635837330](https://github.com/te9no/zmk-config-MKB2/actions/runs/32635837330), and the [hardware validation record](https://github.com/te9no/zmk-config-MKB2/blob/zmk-0.4/docs/zmk-0.4-validation.md). Closed-unmerged PRs #7/#9/#10 are retained only as historical notes.
- Solstice PRs #4/#5 are merged into `zmk-0.4`. Both halves, OLED including Peripheral battery, DYA Studio, PMW3610, and analog-stick runtime are hardware passed. Stable `main` remains untouched.
- [dongle-display PR #3](https://github.com/te9no/zmk-dongle-display/pull/3) remains Draft and actionable for CI repair, but not eligible for module `main` merge before OLED hardware validation. Stacked PR #4 was closed as superseded after its color experiments failed.
- External [cormoran/dya-studio PR #168](https://github.com/cormoran/dya-studio/pull/168) remains open and is tracked only as a pending upstream validation/user decision. Fleet does not alter it.
- External englmaxi/zmk-dongle-display [PR #37](https://github.com/englmaxi/zmk-dongle-display/pull/37) was withdrawn/closed without merge; it is historical evidence, not a current dependency.
- MLX90393 remains explicitly out of scope. Its Draft PR is untouched.

## Prioritized next actions

1. **Cornix / PR #3 — highest waiting priority:** attach the Madula trackball, verify PMW3610 direction/local diagnostics/frame capture, then verify the 1200-baud boot transition. Completion requires all hardware checks before reconsidering the Draft for `zmk-0.4`.
2. **SAA dedicated branch — active:** flash the 21-target branch artifacts to the required JOY/IQS halves and verify direction/cadence, 60-second oversampling coexistence, local/split input, both-half connectivity, CDC boot, and DYA Studio. No stable `master` promotion is planned.
3. **Polaris / PR #7 — waiting:** safely identify and flash the right TB/TPD/IQS hardware, then confirm CDC Debug, 1200-baud boot, COM recovery, split, and module input.
4. **dongle-display / PR #3 — active:** repair the ZMK 0.4/LVGL9 CI in a safe scope. Hardware remains a separate merge gate.
5. **External PR #168 — waiting:** leave the external PR untouched and record the upstream/user decision when it arrives.
6. **Polaris JOY and PMW3610, then SAA PMW3610 — hardware backlog:** CI/build evidence exists, but pointer behavior, split relay, and Studio source diagnostics remain unverified on the relevant modules.
7. **CaGiMe and the lowest-priority group — later:** classify local-only/legacy configurations after the active and hardware-blocked work. Stable firmware `main`/`master` promotion is not a next action.

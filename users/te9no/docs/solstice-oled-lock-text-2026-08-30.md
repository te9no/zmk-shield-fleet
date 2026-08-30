# Solstice OLED lock text removal — 2026-08-30

The owner reported that `NLCK` overlapped other OLED objects and requested its
removal. In `work/solstice-xiao-pinmux`, added
`CONFIG_ZMK_HID_INDICATORS=n` to `Solstice_L.conf` with a comment. This hides the
lock-text widget (Num/Caps/Scroll Lock labels); key behavior is unchanged.
Bongo Cat, battery levels, output status, and modifier indicators are retained.
No display-module or pin-assignment edits were made. The existing unrelated
SVG working-tree change was left untouched.

## Source and build evidence

- Base firmware source: `643a2568e7bb14ed5cca7d513f4d8baa09334a62` plus the above
  **uncommitted** two-line config/comment change. Not a new merged revision.
- Modified `Solstice_L.conf` SHA-256:
  `a8c051fa7d373105e0d87b356f3589d7b27dbc3ec90f3bee5e43e462570bac7d`.
- Initial `just.sh` attempt stopped before compilation because Docker was
  unavailable. After the owner started Docker, the unchanged root `just.sh`
  successfully built **both left US and left JIS**, pristine, with zero failures.
- Command: `./just.sh --profile solstice-xiao-pinmux build-fast Solstice_L_ --pristine=always`.
  Separate build directory `build-oled-no-lock` and artifact suffix
  `codex-zmk-0.4-xiao-pinmux_oled-no-lock` preserve the pin-release baseline files.
- Both generated configs disable HID indicators, preserve Bongo Cat, battery,
  modifiers, compact layout, Peripheral battery proxy, USB logging and CDC boot.
  The lock-text widget object is absent from both build graphs.
- Both generated DTS files are byte-identical to the respective `643a256`
  baseline. Each UF2 passes nRF52840 family, block uniqueness and application
  address-range checks; exported artifacts match the build outputs exactly.

| Artifact | SHA-256 | Blocks |
| --- | --- | --- |
| Left US | `b1c151397da708832a3c1e83f72db52850d0d684174fa2b04455ccb7ef8929f6` | 2236 |
| Left JIS | `21927b61dcac71c969807b011a152779a019b0d618751481c368492d50f8e9c9` | 2236 |

## Hardware

The identity-checked left COM73 entered bootloader via 1200 baud. The left US
artifact above was copied to the bootloader belonging to that same device;
COM73 subsequently reopened at 115200 baud and the Zephyr boot banner was
captured. The bootloader volume disappeared. The right was not reflashed and
remains on the original `643a256` right US image.

The boot capture also contains three `settings: set-value failure` messages
for stored keymap entries (error `-22`) and five runtime local-ID resolution
errors after settings load. Their relationship to this display-only change is
not established. No settings reset, keymap rewrite, or attempted repair was
performed. The later user confirmation establishes observed usability, not
resolution of these saved-settings errors or a save/reload round-trip test.

The owner was notified immediately after flashing and asked to inspect the OLED.
They reported **「OK消えました 他も動作問題ないです」**. Visual acceptance and
representative operation of the actual US pair are therefore **passed based
on the owner's report**, not inferred from the build. The pair is left US with
this uncommitted config change and right US at `643a256`; no JIS hardware or
extended-duration acceptance is inferred. The subsequent
[right CDC recheck](solstice-right-cdc-recheck-2026-08-30.md) also passed boot,
recovery, sensor initialization and split connection.

At the time of that hardware test the firmware source edit and ledger were
local/unpublished. Historical CI success at `643a256` was not a CI result for
the extra uncommitted lock-text change.

## Subsequent integration

The exact tested config was committed as `25dbb3f3061f3b5f1c8729025fd15e3b281dd34b`.
Its [CI 33306076773](https://github.com/te9no/zmk-config-GeaconSolstice/actions/runs/33306076773)
passed all five targets, and [PR #6](https://github.com/te9no/zmk-config-GeaconSolstice/pull/6)
merged into `zmk-0.4` at `7f64859869022d5d7b65afdd4aee0a0d1b45a9a2`.
The merged Git tree exactly matches the tested source head. Stable `main` was
not changed. See the [integration record](solstice-pinmux-integration-2026-08-30.md).
No new flash, settings reset, JIS hardware or long-duration test is claimed.

Private build logs, generated checks, artifact hashes, flash record and filtered
boot log: `.zmk-workspace/evidence/solstice-oled-no-lock-20260830/`.

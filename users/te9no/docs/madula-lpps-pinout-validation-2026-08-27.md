# Madula LPPS pinout validation — 2026-08-27

The Madula J4 LPPS role mapping is P1.12 MOSI, P1.13 MISO, P1.14 DRDY, and
P1.15 SCK. The MeKaBu LPPS host connector has no CS; CS is tied to ground.
The prior generic-SPI allocation (SCK P1.13, MOSI P1.15, MISO P1.14, CS P1.12)
does not match this connector. This correction is scoped to Madula LPPS and
does not change the completed Madula trackball result, DYA, LED, ADC gain, or
driver revision.

Commit [`373edbcb9c9a9909040fa4a3c896ee73facf64b1`](https://github.com/te9no/zmk-keyboard-cornix/commit/373edbcb9c9a9909040fa4a3c896ee73facf64b1)
on `codex/madula-lpps-pinout` is based on `main@794987c`.

- A clean adapter `just.sh` build of `madula_trackpoint` passed at 22:11:48 JST.
  The UF2 is 638,976 bytes, SHA-256
  `37fb49c032e37e53b70fe3d29bef0df86929e8764c6824df8c65ca50b1791c4f`.
- Generated DTS/config and the local source audit passed. SPI default/sleep uses
  SCK P1.15, MOSI P1.12, MISO P1.13, no CS, and preserves mode 1, 1 MHz, and polling.
- At 22:12 JST the independently identified Madula entered `H XIAO-SENSE`
  and was flashed through COM447 at 1200 baud. COM447 is the LPPS CDC Debug
  endpoint; COM445 being unresponsive is not evidence of a LPPS failure.
- The retained boot log SHA-256 is
  `b5e4fef8716e40a44b668402ea6638490c639a7795ae2aa86cf61ad5f90ef153`.
  It confirms boot, USB endpoint, ADS initialization, both channel setups,
  calibration averages 58100/65375, and the polling loop. The expected warning
  is that the DRDY GPIO is not configured and timed polling is used.

The user confirmed movement on `373edbc`, but reported **「90度傾いてる上に入れると左に行く」**. This revision failed orientation; the correction and its acceptance are recorded below. LPPS Studio is not present
in this firmware and is not a validation gate; a COM447 Studio-style response
of zero would be non-diagnostic.

The replacement [`819f6e7f3480a470c01573194c6d4ce790d6df71`](https://github.com/te9no/zmk-keyboard-cornix/commit/819f6e7f3480a470c01573194c6d4ce790d6df71)
uses `x=-ADC1, y=-ADC0`, mapping `(newX, newY)=(-oldY, oldX)`. Its clean
`madula_trackpoint` build passed at 22:17:42 JST; the 638,976-byte UF2 SHA-256
is `a8bd1831e8e5a4f86b149633063e4fe99b04ed3cfabdae283acc81250793014f`.
Source/generated DTS/config and direction audits passed. At 22:18 JST it was
flashed through COM447 at 1200 baud; boot diagnostics, USB endpoint, ADS init,
ADC1/ADC0 channel setup, and calibration averages 65712/58484 were observed.
The boot-log SHA-256 is `43cec627b2bf8c131e2ec38a85e887fffd788b59eca1a605dddbdaabfccf3564`.
The user confirmed **「方向はOKです」**, but reported movement constrained to the
four cardinal directions. Orientation therefore passed on this revision;
unrestricted XY movement did not. A keymap-drawing CI success is not treated
as a firmware-build pass.

The latest [`81644c2608da34a483209f0512fa8291f701b3ce`](https://github.com/te9no/zmk-keyboard-cornix/commit/81644c2608da34a483209f0512fa8291f701b3ce)
removes only `dominant-axis-lock`. The property is absent from the generated
DTS, and the generated C header explicitly defines
`DT_N_S_analog_axis_hires_0_P_dominant_axis_lock` as `0`.
Direction remained unchanged from user-accepted `819f6e7`. After this flash,
the user confirmed **「すごい、かんぺき」**, accepting direction and unrestricted
XY/diagonal input. Clean build, audit, and COM447 flash/boot passed at
22:21:30/22:22 JST; UF2 SHA-256 is `15e79ee5814df791c2ea709945c4d5500ed09c96e87ffd12aef7bffab3b0b088`,
boot-log SHA-256 is `110feed37c79ed85cd8e8f779a0bb751a1c6cf42ceb2a502924c6756257f6bab`,
and CI [33076389402](https://github.com/te9no/zmk-keyboard-cornix/actions/runs/33076389402) is pending.

Hardware acceptance is complete for this LPPS revision. Firmware CI is a
separate pending gate, and no firmware-main merge has been performed.

# Polaris pin-release hardware validation

Date: 2026-08-27

The owner identified the connected modules as **left JOY / right TB** before flashing the UF2 files built from source [`8421728`](https://github.com/te9no/zmk-config-GeaconPolaris/commit/84217286bbc5d064b1d6a3e3b3f671017e687942) on `codex/zmk-0.4-xiao-pinmux`. This report separates firmware transfer, boot/CDC/split connectivity, and actual module operation. A successful build or flash is not a successful sensor test.

## Flash and boot results

| Side | Trigger and bootloader | Result | Not yet verified |
| --- | --- | --- | --- |
| Left JOY | Studio COM326 at 1200 baud → H drive → Debug COM325 | UF2 written; debug port returned; Zephyr boot banner observed. | JOY movement, direction/speed/continuity and OLED visual appearance. |
| Right TB | COM327 at 1200 baud → I drive → COM327 | UF2 written; CDC and Zephyr boot returned; BLE split connection established. | Pointer/module input. PMW3610 initialization failed as detailed below. |

The earlier left-side trigger attempt on Debug COM325 did not enter the bootloader. COM326, the Studio endpoint, is the working trigger port for this firmware. This port-selection result is not classified as a CDC hardware failure. Split connection success does not prove sensor reports were relayed.

Local CDC evidence is retained under the log basenames `hardware-left-joy-flash.log` and `hardware-right-tb-flash.log`. The public ledger records the relevant observations without publishing local absolute paths or unrelated device identifiers.

## Right TB sensor failure

On the new `8421728` firmware:

- The 3-wire controller initialized and startup transfers reported result `0`.
- OBSERVATION read `0xff` and Product ID read `0x00`, not the expected `0x3e`.
- PMW3610 initialization failed at step 2 after the initial attempt plus 10 retries, 11 attempts in total.
- CDC, boot and the BLE split connection still worked. These successes do not clear the sensor-initialization failure.

The cause is not established. Transfer result `0` only reports that the controller completed the transaction; it does not establish that the sensor returned valid data.

## Comparison rollback

Only the right half was reflashed with the previous `zmk-0.4` distribution UF2. Its size is **616,960 bytes**, and its SHA-256 is:

```text
2dbb49c0036be7dbf3d2fa94b2137acac471bc646ce35ba779eab31f81186f78
```

The diagnostic comparison confirmed that this hash matches the distribution UF2 at maintenance revision `ed5cba4`; it is not merely a similarly named local file.

The baseline flash used COM327 → I and successfully returned to CDC/Zephyr boot and split connectivity. However, **the same OBSERVATION `0xff`, Product ID `0x00`, and step-2 failure after 11 attempts occurred**. Evidence is retained as `hardware-right-tb-baseline.log`.

The rollback/comparison procedure is complete, but it did **not** recover PMW3610 operation. Reproduction on both the old and new UF2 means a regression caused by the XIAO pin-release change has not been demonstrated. This comparison also does not prove a specific electrical or firmware root cause.

The diagnostic source comparison found matching SHA-256 values for the old/new 3-wire C implementation; the `TB_R` overlay/config differ only in line endings. As a hypothesis, OBSERVATION command `0x2d` ending in bit 1 followed by `0xff`, and Product-ID command `0x00` ending in bit 0 followed by `0x00`, are consistent with an undriven SDIO line retaining the final command level. This is **not a confirmed diagnosis** of wiring, power, or sensor failure.

## Right TB BLE restore

At **2026-08-27 21:02:45 JST**, after the user ended the ESB experiment, the
right half was restored to the normal BLE `8421728` UF2. `COM327` at 1200 baud
entered drive `I`; the copy completed for serial `07410F37C96F9FEF`. `COM327`
then returned with a Zephyr boot record and **PMW3610 initialized at CPI 800**.
The filtered CDC evidence is retained as
`hardware-ble-restore-8421728-right-boot.log`.

This is a new passed right-sensor-initialization observation for `8421728`. It
does not erase the earlier `8421728` or `ed5cba4` failed observations, prove a
cause for their differing outcomes, or prove pointer input.

## Matched BLE restore and Studio RPC

After the DYA client released COM326, the left `8421728` UF2 copy completed
through `COM326` → `H` using serial `7192CB7FFA85E5D1`; `COM325` then returned
with a whitelisted boot banner observed at **21:04:23.687 JST**. The
right link capture recorded a BLE security callback at **21:04:23.401 JST**.
Both halves therefore run the matched normal-BLE `8421728` pair. The retained
boot/link logs are `hardware-ble-restore-8421728-left-boot.log`,
`hardware-ble-restore-8421728-right-boot.log`, and
`hardware-ble-restore-8421728-right-link.log`.
Their SHA-256 digests are, respectively,
`f42cccc904376df33e102b135bbaeeb539fff81897bb586b97c566ab360fc145`,
`20b74333119ee47afbeb02cd2a6958d45e6e18af2006d467406b108e0ab9d6f1`, and
`e2e086d44e7bcc5f3057ff258b22c11997d2b2d56181d0ba1a0b7f87732f609a`.

At **21:05:23.552 JST**, a read-only native Studio probe on COM326 at 12500
baud enumerated the PMW subsystem at index **2** (not the retired ESB index 0).
A source-1 GetInfo request received an immediate deferred response and a
PeripheralResponse for request 1: Device ready, Product ID `0x3e`, revision
`0x01`, no reported init error, runtime CPI 800, and the right-TB settings ID.
The safe read-only frames were
`AB0A0F0802A2060A1208080212044A020801AD` and
`AB1242A2063F0A3D080212391237080110011A31122F0A2D0801103E18012A1C08A00620012801300138800140882748E884015028586460F403680E3A0772696768747462AD`.
This passes the normal-BLE remote PMW read RPC and supports the observed split
connection. No settings write, stream, or keymap dump was performed.

This is a complete firmware-pair restoration, not a complete hardware
acceptance: physical left-JOY/right-TB input and left OLED checks remain pending.

- Both halves run normal BLE `8421728`; their boot, split, right PMW initialization, and remote read RPC are recorded above.
- Left JOY input/OLED visual appearance and right TB pointer/module input remain unverified.
- Do not mark overall hardware passed until the physical input and OLED checks are complete.
- No firmware source change, maintenance/stable merge, or firmware PR was made for this comparison.
- The successful right-TB pointer/split observations recorded on 2026-08-26 remain historical evidence. This report preserves the earlier failed observation and baseline comparison alongside the later recovery; it does not transfer any historical result to the current physical-input session.

## Left JOY orientation failure

On the matched normal-BLE `8421728` pair, the user physically tested the left
JOY and reported that **physical LEFT moved the cursor UP**. This is a 90-degree
wrong orientation. The result is a failed physical module-input observation for
the left JOY at `8421728`; it does not invalidate the separate right-TB boot,
BLE, PMW initialization, or read-only Studio RPC evidence at that revision.

## Left JOY orientation candidate

The first experimental `codex/zmk-0.4-xiao-pinmux` candidate
[`8de9473ba6fc229283fed2c8866ec80609e77b5d`](https://github.com/te9no/zmk-config-GeaconPolaris/commit/8de9473ba6fc229283fed2c8866ec80609e77b5d)
changed only `snippets/JOY/JOY.overlay` (three insertions and one deletion) to
use `XY_SWAP | Y_INVERT`, which maps `(newX, newY) = (oldY, -oldX)`. Its
left-only build and boot passed, but the user reported **「上下逆、左右も逆」**:
the JOY direction test failed. The user also reported **「OLED、TBはOKです」**;
that records a left OLED pass at `8de9473` and a right-TB physical-input pass
at unchanged `8421728`, not a left-JOY pass.

The replacement source candidate
[`8de074a06c5bdca580fd4f1b26dc03647d41a10d`](https://github.com/te9no/zmk-config-GeaconPolaris/commit/8de074a06c5bdca580fd4f1b26dc03647d41a10d)
uses `XY_SWAP | X_INVERT` (param3). The published branch head
[`1fdc244ce05d593abb71f8c3b04bf7d6f851c5dc`](https://github.com/te9no/zmk-config-GeaconPolaris/commit/1fdc244ce05d593abb71f8c3b04bf7d6f851c5dc)
publishes that source and preserves the earlier `8de9473` CI artifact
`615f53a`; it is not evidence of a new right-side build.
ADC, pointer speed, and trackball settings are unchanged.

- A left-only incremental `just.sh build-fast` build passed for
  `Polaris_L_MODULE_JOY` at 2026-08-27 21:37:05 JST. The produced UF2 is
  999,936 bytes with SHA-256
  `6de57ae4ce58c23364ea58670d23d5ecda266e80a5a5cf31510a46924c3579c0`.
- The overlay/cardinal-vector audit and generated-DTS rotation check passed;
  the preservation audit reported 101 assertions. This is left-only evidence:
  the other seven DTS outputs remain evidence from `8421728`, not fresh
  candidate builds.
- At 2026-08-27 21:38:59.488 JST, only the left UF2 was copied through
  COM326 at 1200 baud to drive H (serial `7192CB7FFA85E5D1`); Debug COM325 and
  Studio COM326 returned and the filtered boot banner was observed. The retained
  boot log SHA-256 is
  `1dbfec224d0f8e4f11662c790fa361c388a9196d5f619f2c80ba999bdcded3df`.
- The boot alone did not establish JOY input. The user subsequently accepted
  the `8de074a` JOY direction and reported **「長時間動作もOKです」**. No
  duration, speed measurement, or per-direction measurement is claimed. CI run
  [33072085319](https://github.com/te9no/zmk-config-GeaconPolaris/actions/runs/33072085319)
  for the earlier `8de9473` candidate succeeded; the latest source/artifact
  head CI run [33072906476](https://github.com/te9no/zmk-config-GeaconPolaris/actions/runs/33072906476)
  is in progress.

The right half was not rebuilt or flashed for this candidate. It remains on
`8421728` with UF2 SHA-256
`296aad41178784752b89ebb94fd9dbe0f1fc38191f5462eaf4f06eaf02976d52`.
Therefore `8de9473` is not a newly matched left/right build and does not update
the right-TB physical-hardware status. ESB remains retired and disabled.

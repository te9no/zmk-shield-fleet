# Cross-repository audit — 2026-08-21

> **Historical snapshot:** This document preserves the 2026-08-21 initial
> inventory and must not be read as current status. See
> `pr-ledger-audit-2026-08-24.md`, `fleet.toml`, and `changes/*.json` for the
> authoritative maintenance branches, validation evidence, and next actions.

Polarisの実証済み構成を基準に、ローカルの開発branchと各リポジトリの
`config/west.yml`、関連snippet／shieldを横並び確認した初回棚卸しです。

CornixはMadula module snippet方式として管理し、IQS9151、LPPS、trackballの
Madula向け共通変更に参加します。

| Repository | IQS本家/ZMK 0.4 | Analog電圧oversampling | CDC Zephyr 4.1 | DYA Studio V2 |
| --- | --- | --- | --- | --- |
| Polaris | applied | applied | applied | applied |
| MKB2 | n/a | validation branch・実機待ち ([#7](https://github.com/te9no/zmk-config-MKB2/pull/7)) | validation branch・実機待ち ([#7](https://github.com/te9no/zmk-config-MKB2/pull/7)) | validation branch・実機待ち ([#7](https://github.com/te9no/zmk-config-MKB2/pull/7)) |
| SparAkashaAnanta | validation branch・実機待ち ([#2](https://github.com/te9no/zmk-config-SparAkashaAnanta/pull/2), [revert #6](https://github.com/te9no/zmk-config-SparAkashaAnanta/pull/6)) | validation branch・実機待ち ([#4](https://github.com/te9no/zmk-config-SparAkashaAnanta/pull/4), [revert #6](https://github.com/te9no/zmk-config-SparAkashaAnanta/pull/6)) | validation branch・実機待ち ([#3](https://github.com/te9no/zmk-config-SparAkashaAnanta/pull/3), [revert #6](https://github.com/te9no/zmk-config-SparAkashaAnanta/pull/6)) | validation branch・実機待ち ([#3](https://github.com/te9no/zmk-config-SparAkashaAnanta/pull/3), [revert #6](https://github.com/te9no/zmk-config-SparAkashaAnanta/pull/6)) |
| Cornix | applied ([#1](https://github.com/te9no/zmk-keyboard-cornix/pull/1)) | n/a | applied（repository内同等実装、[#1](https://github.com/te9no/zmk-keyboard-cornix/pull/1)） | applied ([#1](https://github.com/te9no/zmk-keyboard-cornix/pull/1)) |
| GeaconSolstice | n/a | validation branch・実機待ち ([#1](https://github.com/te9no/zmk-config-GeaconSolstice/pull/1)) | validation branch・実機待ち ([#1](https://github.com/te9no/zmk-config-GeaconSolstice/pull/1)) | validation branch・実機待ち ([#1](https://github.com/te9no/zmk-config-GeaconSolstice/pull/1)) |
| GeaconSparagmos | n/a | pending | pending | pending (旧stack) |

## Registered triggers

- IQS: Polaris `839f0c0`でShiniNet本家を検証し、`f3e2337`、`b95a554`で調整。
- Analog voltage: module `59fc126`をPolaris `6a7b21f`でpinして検証。
- CDC: Zephyr 4.1 edge-trigger修整 `1850754`をPolaris `1088543`でpinして検証。MKB2 PR #7では全左centralでCDC Debug（ZMK log level 4）を明示的に有効化し、16/16 build成功。2026-08-22にMKB_L_MODULE_KEY実機でdebug出力と1200 baud UF2遷移を確認。
- DYA Studio V2: Polaris `e11afa1`を基準とし、Cornix `e8dc0e1`でも同じ固定revision群を採用。
- Revision pinning: moving ref／短縮SHAはPolaris、MKB2、SAA、Cornix、GeaconSolsticeが0件。残るlegacy repositoriesの現行値は`west-revision-pinning`台帳を参照する。
- MKB2 ZMK 0.4 + DYA Studio V2: PR #7で15 firmware variantとsettings_reset（16/16）が成功。非LPPS左centralへフルstack、右側へwatchdog/kscan診断relayを導入し、左LPPSはRAM制約からフルStudio対象外。MKB2 buildは成功したが、module実機検証前のためclean Draftを維持した。
- GeaconSolstice ZMK 0.4: PR #1の全5 firmware targetが成功。te9no forkの[LVGL 9 PR #3](https://github.com/te9no/zmk-dongle-display/pull/3)はDraftのままで、現在`west update` CI failureを調査待ち。積み上げ[PR #4](https://github.com/te9no/zmk-dongle-display/pull/4)の明示色/mono themeはSolstice OLED実機で不合格だったためsupersededとしてcloseし、Solsticeは実機合格済みの上流`englmaxi/zmk-dongle-display@2bb333f`を維持する。
- Historical follow-up: englmaxi/zmk-dongle-display [PR #37](https://github.com/englmaxi/zmk-dongle-display/pull/37) was withdrawn and closed without merge. It is not a current dependency.

## Inventory findings

GeaconSolstice、GeaconSparagmosが旧DYA stackを利用していたため、初期fleetの対象漏れとして
追加しました。MKBtestは`te9no/zmk-config-MKB2`をoriginにする
試験checkoutであり、独立した配布先ではないため重複登録していません。

この表は「導入候補」を示し、各機種への無条件適用を意味しません。`pending`はbuildと
実機確認を経て`applied`へ更新するか、ハードウェア／運用上不要なら理由を添えて
`not-applicable`へ更新します。

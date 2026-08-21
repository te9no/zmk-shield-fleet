# Cross-repository audit — 2026-08-21

Polarisの実証済み構成を基準に、ローカルの開発branchと各リポジトリの
`config/west.yml`、関連snippet／shieldを横並び確認した初回棚卸しです。

| Repository | IQS本家/ZMK 0.4 | Analog電圧oversampling | CDC Zephyr 4.1 | DYA Studio V2 |
| --- | --- | --- | --- | --- |
| Polaris | applied | applied | applied | applied |
| MDK | n/a | pending | pending | pending |
| MKB2 | n/a | pending | pending (旧revあり) | pending (一部旧stack) |
| MRM | n/a | pending | pending | pending |
| SparAkashaAnanta | pending (fork/ZMK 0.3) | pending (moving main) | pending (moving main) | pending (ZMK 0.3) |
| Cornix | applied | n/a | pending | applied |
| Torabo | n/a | n/a | pending (v0.2) | pending (ZMK 0.3) |
| CaGiMe | pending (fork/ZMK 0.3) | pending (moving main) | pending (comment only) | pending (ZMK 0.3) |
| Berkut51 | n/a | pending | pending | pending (旧stack) |
| GeaconSolstice | n/a | pending | pending | pending (旧stack) |
| koZakura | n/a | n/a | pending | pending (旧stack) |
| GeaconSparagmos | n/a | pending | pending | pending (旧stack) |

## Registered triggers

- IQS: Polaris `839f0c0`でShiniNet本家を検証し、`f3e2337`、`b95a554`で調整。
- Analog voltage: module `59fc126`をPolaris `6a7b21f`でpinして検証。
- CDC: Zephyr 4.1 edge-trigger修整 `1850754`をPolaris `1088543`でpinして検証。
- DYA Studio V2: Polaris `e11afa1`を基準とし、Cornix `e8dc0e1`でも同じ固定revision群を採用。

## Inventory findings

Berkut51、GeaconSolstice、koZakura、GeaconSparagmosが旧DYA stackを利用していたため、
初期fleetの対象漏れとして追加しました。MKBtestは`te9no/zmk-config-MKB2`をoriginにする
試験checkoutであり、独立した配布先ではないため重複登録していません。

この表は「導入候補」を示し、各機種への無条件適用を意味しません。`pending`はbuildと
実機確認を経て`applied`へ更新するか、ハードウェア／運用上不要なら理由を添えて
`not-applicable`へ更新します。

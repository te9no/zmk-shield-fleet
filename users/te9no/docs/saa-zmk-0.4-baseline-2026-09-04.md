# SAA ZMK 0.4専用ブランチ集約（2026-09-04）

## 結果

SAAの分散したZMK 0.4検証成果を正式な開発ブランチ [`zmk-0.4`](https://github.com/te9no/zmk-config-SparAkashaAnanta/tree/zmk-0.4) へ集約した。stable `master`、実機、第三者repositoryは変更していない。PRも作成していない。

- 3-wire SPI対応source `c9f6779`を集約元とし、XIAO qualifier・未使用peripheral解放 `0540667`と同じ変更を`5d67222`として取り込んだ。
- 日次build-healthファイルのcommitをsource `28c3546`で停止。GitHub Actionsの標準状態を利用し、既存の古いbadge資産は今回削除していない。
- CI生成commitは`1f702fc09fbf3578c9b01d8bce13224a620658a2`。branch専用folderへ21 UF2を格納した。

## 含まれる基盤

- cormoran ZMK `e5c9b6915b56801193e359dd9bad4a167ce0d1b8`。
- cormoran PMW3610 custom Studio RPC driver `5c34ea0eec246a1c986111417cd779b53144629a`。
- te9no 3-wire SPI controller `4362133dbfbf66788b66b0a3e3c410b9232c06cb`。
- ShiniNet IQS9151 driver `08a6fd19c5aa5ae7f11daf371b5a391cd8596783`。
- 電圧監視oversampling `59fc126f859d4e7700186c9906e4645379763c34`。
- Zephyr 4.1 CDC boot trigger `1850754d269aab9ba73e4639371bfe59a4130e65`。
- `xiao_ble//zmk` qualifier、JOYへのoversampling snippet、右手CDC Debug／Studio snippets、SAA共通DTSの未使用peripheral解放。

## ビルド証拠

workspaceの`just.sh`を専用設定パスと固定manifestで実行し、20 module variant＋settings resetの**21/21 pristine buildに成功**した。ログはローカル生成領域の`build-parallel-20260904-100109`に保持し、公開台帳へローカルパスやraw logは載せない。

[GitHub Actions run 33862051924](https://github.com/te9no/zmk-config-SparAkashaAnanta/actions/runs/33862051924)でも21個すべて成功。各ジョブはfirmwareに加えてKconfigと生成Devicetreeをartifactへ収録し、publish jobが[21 UF2](https://github.com/te9no/zmk-config-SparAkashaAnanta/tree/zmk-0.4/firmware/zmk-config-SparAkashaAnanta/zmk-0.4)をbranchへcommitした。build-health jobはskipされ、badgeへの新規書き込みはなかった。

新規profile初期化はZephyrの不要な全依存を複製し始めたため中断した。途中生成profileは2.2GBで、限定削除は安全ポリシーに拒否されたため迂回削除せず残置。ビルドは既存SAA west環境を新branch manifestへ同期して実施した。このキャッシュ残置はsource／CI結果には影響しない。

## 未確認

ビルド合格を実機合格には転用しない。次は`zmk-0.4`のartifactを用い、代表variantの1200-baud boot、DYA Studio、左右split、OLED/LED、JOY、TB/PMW3610などを確認する。左右TPD+IQSの既知pin ownership/wiring課題は別件のまま維持する。

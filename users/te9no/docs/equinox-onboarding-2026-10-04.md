# GeaconEquinox Fleet登録

管理対象: te9no/zmk-keyboard-GeaconEquinox。管理ブランチはmain。
登録時のローカルHEAD: 9b3b91b18524b088716f51a41509513868f03eca。
未コミット変更を含むため、HEADだけで下記の成果を再現できるとは扱わない。

## 構成

- XIAO BLE / ZMK qualifier、左右US/JISの4構成。
- 左PAT9125EL: sekigon-gonnoc/zmk-driver-hires-dial。
- 右PMW3610: cormoran custom Studio RPCドライバ、3-wire SPI構成。
- config/west.ymlのZMK参照はcormoran。CDC logging/boot用snippetを左右で使用。
- JOY/LPPS/IQSは搭載構成に含めず、これらの専用キャンペーンには登録しない。

## 今回までの証跡（コード・ビルドと実機を区別）

- ローカルDYA拡張: device info、watchdog、kscan diagnostics、runtime macro/combo、
  BLE管理、Settings RPC、runtime input processor等を追加。未コミット・未push。
- 4構成ビルド成功ログ:
  .zmk-workspace/profiles/geacon-equinox/logs/build-parallel-20261002-235129/
- 続くLayer 1スクロールY反転は左US/JISビルド成功:
  .zmk-workspace/profiles/geacon-equinox/logs/build-parallel-20261002-235923/
- 左USはCDC 1200 baud経由で書き込み済み。PAT readyと右入力の受信ログを確認。
- 右側はポート使用中で新しいDYA拡張版を書き込めていない。JISの実機確認も未実施。
- Studioの各画面、Layer 1スクロール修正後の方向、dial操作の最終受入は未確認。
- MeKaBuのマクロ割当・コンボ電源断問題をEquinoxでも再現したとは扱わない。

## 管理方針

全機種共通6項目とtrackball向けPMW3610項目に追加。
DYAのローカルビルドと左US flash以外の共通受入条件は再監査待ち。
従来の他機種の合格証跡は転用しない。自動横展開は無効。
次は公開対象差分のレビュー、右側flashの承認・実施、Studio実機確認。

# MeKaBu Studioクレーム対応（2026-10-04）

対象はmkb2のみ。報告元の実機ファームrevisionは未確認。
公開zmk-0.4の7b02e9bcf512dd6a494ed94cb1be2f02466213f3から
ローカルcodex/mkb-studio-persistenceを作成。修正は未コミット・未push。

## 記録

- Shift付きキー割り当て: 対応実装はある。UIでの再現・保存・実入力は保留。コード変更なし。
- マクロ: rmacro定義不足を確認。Studio snippetへbehaviors/runtime_macro.dtsiを追加。
- コンボ: UI上のデータ表示と実行キャッシュを区別。設定読込完了でキャッシュを再構築する補正をMeKaBu内に追加。
  起動時レースは原因候補であり、クレーム実機で確定したものではない。

## ローカル証拠

- ソース: config/zmk-config-MKB2/src/runtime_combo_boot.c、tests/test_studio_persistence.py。
- ホスト回帰テスト3件成功。実Cコールバックとイベント／保存状態の代替を使ったテストであり、実機の電源断再現ではない。
- just.sh --profile mkb-studio-persistence build-fast MKB_L_MODULE --pristine=always: 左7構成成功。
- ログ: .zmk-workspace/profiles/mkb-studio-persistence/logs/build-parallel-20261004-005734/。
- JOYの生成DTSにrmacro、リンクマップに補正関数と設定読込完了イベント購読を確認。
- UF2: firmware/zmk-config-MKB2/codex-mkb-studio-persistence/。

## 次の確認

修正をレビューし、承認後にコミット・公開、対象機を書き込む。
マクロ作成→割り当て→実行、コンボ保存→USBと電池を外して起動→再保存せず動作、
起動時キー押下の有無、Studio新規接続からの読み直しを個別に確認する。
Shift付きキーは報告元のUI操作とOS配列・Layout Shift状態も記録する。
他キーボードへの横展開・上流PRは行っていない。効果確認後に共通採用先の監査対象を判断する。

# Madula LPPS: CDC復帰確認とStudio/LED項目完了（2026-09-01）

## 対象

LPPSへの付け替え依頼に対する所有者の「どうぞ」を受け、[前回確認済みのLPPS版](madula-lpps-studio-validation-2026-08-31.md)を書き込み、続いてLPPS自身から同一firmwareへのCDC再書き込み・復帰を確認した。

- [公開UF2](https://github.com/te9no/zmk-keyboard-cornix/blob/b3191a46da203c557091bb3248209f7280a07633/firmware/zmk-keyboard-cornix/main/madula_trackpoint.uf2): artifact `b3191a46da203c557091bb3248209f7280a07633`、882688 bytes。
- SHA256 `4e5798bd773985b600fbd06e73577ef8e7bbbf8a6717392445bc7f5143c68215`。
- ソースは統合済みPR #7。今回は既存artifactの検証であり、新規ビルド・firmwareソース編集・settings reset・他キーボードの書き込みはしていない。

## 実測と所有者確認

1. COM454/COM447のUSB親シリアルと対象Madulaの一致を確認。1200 baudでブートローダーを起動し、H: XIAO-SENSEのシリアル・board IDを照合した。
2. 最初は既存IQS applicationが1745/1745ブロック一致することを確認してLPPS版をコピー。直後の検査はCOM列挙の待機判定が早すぎて停止したが、後続のCIM照会で同じMadulaのCOM445/447/454復帰を確認した。これは検査側の待機処理を修正し、firmwareは変更していない。
3. LPPSで起動した状態からCOM454を1200 baudで再度操作。識別済みH: CURRENT.UF2のapplication範囲をLPPS UF2と比較し、**1724/1724ブロック一致**。全flashやsettingsのコピーは保存していない。
4. 同じLPPS UF2を再書き込みし、コピー完了を確認。復帰したCOM454/COM447をUSB親シリアルで照合し、115200 baudで再openできた。
5. Studio core get-device-info（request ID 66）から、対象Madulaの名前・シリアルが一致する**28-byte応答**を検証した（2026-09-01 00:16 JST）。
6. Debugログ本文を**1006文字受信**。analog_axis_hires、BLEリンク状態、LEDのログを確認。`TRAP 3: Timeout Triggered for LED 0! Returning to base_color.` というwarningも含まれるため、「warningなし」とは記録しない。通信復帰の合格とログの全内容が正常であるという判定は区別する。
7. 作業中、所有者から「大丈夫もんだいない」と通常動作の確認を得た。これは所有者申告であり、ツールによる入力検査とは区別する。

全ポートを閉じて解放した。現在のfirmwareはLPPS版。LPPS自身のCDCブート・同一UF2への再書き込み・Debugログ受信・Studio基本通信を合格とする。

## 完了範囲

[TB](madula-tb-orientation-validation-2026-08-31.md)、[IQS](madula-iqs-cdc-recovery-2026-09-01.md)、本LPPS記録により全3種類のCDC復帰が確認できた。既存の各variantの入力・Studio接続・LED所有者確認と合わせ、`madula-studio-status-led` の全validationを合格とし、対応するnext actionを完了一覧の根拠を残して除去する。

IQSのgesture・cold-start・長時間動作・split接続の別件や、TBセンサー画像取得などの追加検証は完了扱いにしない。

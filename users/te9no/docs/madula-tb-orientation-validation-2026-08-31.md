# Madula TB: 方向・Studio・CDC再確認（2026-08-31）

対象はCornixのMadula TB版のみ。LPPS/IQSや他リポジトリへは横展開しない。

## 修正とビルド

- [修正PR #7](https://github.com/te9no/zmk-keyboard-cornix/pull/7)、source `c7e2a06a6609eb3ad2a8c3a75159928f914701ad`。
- 基点: `main@d899063c78debfc40fd378b17f491e3386c0bb5d`。
- 所有者の「上へ動かすと左」「右へ動かすと上」という報告から、取り付け補正をX反転のみ（`0x2`）からXY入れ替え＋両軸反転（`0x7`）へ変更。標準TBとStudio用の両overlayを揃えた。
- 入力ドライバ、LPPS/IQS、保存済み設定は変更していない。
- `just.sh --profile madula-lpps-validation build-fast madula_trackball --pristine=always` が成功。専用worktreeと`build-tb-orientation`を使用。
- 生成DTSで`0x7`、configでStudio、PMW Studio RPC、CDC logging/boot trigger有効を確認。
- 6件のhost/config試験成功。方向試験は旧補正と報告された動きから推定した入力値によるモデル試験であり、実機測定とは区別する。
- [修正ブランチCI](https://github.com/te9no/zmk-keyboard-cornix/actions/runs/33399226607): 全12構成・workflow成功。CI生成commit `5246917cf3b90e57b948e83239cfb25899c59c3c` はsourceとの差分がfirmware 12ファイルのみ。
- PR #7を `main@b54f1de0c93b1bfb8636251d48a45645285b29ee` へ統合済み。統合後のtreeと上記CI生成commitのtreeに差分なし。
- [CI公開UF2](https://github.com/te9no/zmk-keyboard-cornix/tree/b54f1de0c93b1bfb8636251d48a45645285b29ee/firmware/zmk-keyboard-cornix/codex-madula-tb-orientation)。続くmain CI33402191691も成功し、[main標準フォルダ](https://github.com/te9no/zmk-keyboard-cornix/tree/b3191a46da203c557091bb3248209f7280a07633/firmware/zmk-keyboard-cornix/main)を再生成済み。

## 実機対象と所有者確認

- 書き込んだローカルUF2: `madula_trackball.uf2`、914944 bytes。
- SHA256: `40d14595c60cd0754ebdb33a3eab275b117b381eed03c5eb6cdac1e5da183226`。
- ビルドはsource commit作成前、同一編集内容で実施。埋め込みrevisionはdirtyな基点を示す可能性がある。CI再生成UF2とのバイナリ一致は主張しない。
- USB機器のシリアルとH:のboard IDを照合して書き込み、COM445 / COM447 / COM454の復帰を確認。
- 「上→上、右→右になったか」に対する所有者の「OKです」を、方向の実機合格として記録。
- PMW3610センサー情報がDYA Studioに表示されるかという確認への「OK完璧です」を、所有者申告のStudio接続・センサー情報表示合格として記録。

## 今回追加依頼されたCDC復帰確認

初回はCOM454が使用中で起動要求を開始できなかった。所有者の「つづけて」後にポート解放を確認し、以下を実測して合格とした。

1. 稼働中のMadula TB候補版にCOM454・1200 baudでブート要求。
2. H: XIAO-SENSEのディスクシリアル・board IDを確認。要求から識別完了まで995ms（OS照会時間を含み、純粋な起動時間ではない）。
3. H: CURRENT.UF2からapplication部分だけを比較し、上記ローカルUF2と**1787/1787ブロック一致**。全flashやsettingsのコピーは保存していない。
4. 同じSHA256のUF2を再書き込みし、コピー完了とCOM445 / COM447 / COM454復帰を確認。
5. COM454を115200 baudで再open。今回はログ本文0文字だったため、ログ出力内容の合格とは区別する。
6. COM447を115200 baudで開き、Studio core get-device-info（request ID 61）に対し、同じMadulaの名前・シリアルを含む28-byte応答を検証。

確認後は両ポートを閉じて解放した。TB版のCDCブート・同一firmware復帰・Studio基本通信を合格とする。LPPS/IQSへの合格の転用はしない。

## 保留範囲

同一variantへのCDC再書き込み・復帰はLPPSのみ未確認。IQSは後続の[CDC確認記録](madula-iqs-cdc-recovery-2026-09-01.md)で合格。入力・Studio・LED表示は後続の[LPPS確認記録](madula-lpps-studio-validation-2026-08-31.md)と[IQS確認記録](madula-iqs-studio-validation-2026-08-31.md)で合格。TBのセンサー画像キャプチャ／ストリーミングは追加確認として保留。

## TBのLED確認

LED確認内容を「内蔵RGBとSPI LEDの併用」「USB接続表示」「レイヤー番号の点滅」と説明した後、所有者から「TBのLEDはOK」と返答を得た。TB版の上記表示を所有者申告の合格として記録する。LPPS/IQSへは転用しない。

# Madula LPPS: DYA Studio接続確認（2026-08-31）

対象は `cornix` の `madula-studio-status-led`、Madula LPPS版のみ。

## コード・ビルド

- [PR #6](https://github.com/te9no/zmk-keyboard-cornix/pull/6) の統合先は `main@fd1ac78d72fe39aee173d3fa678084530a2b35b7`。
- [main CI33384668884](https://github.com/te9no/zmk-keyboard-cornix/actions/runs/33384668884) は成功。
- 公開artifact commit `d899063c78debfc40fd378b17f491e3386c0bb5d` と上記統合commitの差分はfirmwareのみ。
- 使用UF2: [madula_trackpoint.uf2](https://github.com/te9no/zmk-keyboard-cornix/blob/d899063c78debfc40fd378b17f491e3386c0bb5d/firmware/zmk-keyboard-cornix/main/madula_trackpoint.uf2)（882688 bytes）。
- Git blob: `8cc98f5c3a33a392b8c32aa25c772241fb0fd952`。
- SHA256: `22ce8b7475d03807f99a279e1aa3f37d57ba2002a003083e12b51e776a047c57`。

## 書き込み・観測

所有者の許可後、USBシリアルで対象Madulaを識別し、UF2のGit blob・SHA256を照合。
旧版のCOM447から1200-baudでブートローダーを起動した。
H: のディスクシリアルとXIAO Senseのboard IDを確認してから上記UF2をコピーし、コピー完了と再起動を確認した。

再起動後、同じ機器にCOM445 / COM447 / COM454の3本が復帰した。
今回の列挙ではStudio用がCOM447、CDC Debug用がCOM454。
診断ツールで両ポートを115200 baudで開けた。
Studioへの読み取り要求後に受信はあったが、収集処理の型変換エラーにより応答を検証できず、再試行時にはCOM447が使用中だった。
したがって、ツールによるRPC内容確認やブラウザー操作成功の証拠にはしていない。

## 所有者確認

書き込み前の「LPPSはOKです」の後に「DYAStudioにつながらない」と申告があったため、前者はStudio接続合格には用いない。
上記の書き込み完了後、Madula（COM447）での接続を案内したところ、所有者から「OK」と返答があった。
この文脈に基づく**所有者申告のDYA Studio接続成功**として `lpps-studio-hardware = passed` を記録する。

## 保留

- LPPSの今回版での入力回帰、Studio内の編集・保存、LED併用・USB表示・レイヤー番号点滅。
- IQS版のStudio接続、TB版の回帰、各版のLED実機確認。
- 新版からの1200-baud再書き込み・復帰（今回のブート要求元は旧版）。

他のvalidationは変更せず、項目全体を完了にはしない。

## TB検証後のLPPS再書き込み

所有者の「LPPS版書き込んで」に従い、main CI33402191691成功後の公開artifact `b3191a46da203c557091bb3248209f7280a07633` からLPPS版を取得して書き込んだ。

- [使用UF2](https://github.com/te9no/zmk-keyboard-cornix/blob/b3191a46da203c557091bb3248209f7280a07633/firmware/zmk-keyboard-cornix/main/madula_trackpoint.uf2)、882688 bytes。
- Git blob `43e7def463d90364fbb128cd6f8d5b6d360aa83e`、SHA256 `4e5798bd773985b600fbd06e73577ef8e7bbbf8a6717392445bc7f5143c68215` を照合。
- 対象Madulaをシリアルで識別し、TB版のCOM454から1200 baudで起動、H: のシリアル・board ID照合後にLPPS版をコピーした。
- 再起動後、COM454を115200 baudで開け、COM447のStudio core get-device-info（request ID 62）から同じMadulaの28-byte応答を検証。両ポートは解放済み。
- これはLPPSへの書き込み・復帰とStudio基本通信の確認。LPPS自身を起点とするCDC再書き込み試験、今回の入力・LEDの所有者確認はまだ行っていない。

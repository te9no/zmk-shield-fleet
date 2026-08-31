# Madula IQS: Studio・入力・LED確認（2026-08-31）

## 対象とビルド証拠

- 対象はCornixリポジトリのMadula IQS通常版。別variantの合格は転用しない。
- ソース統合: [PR #7](https://github.com/te9no/zmk-keyboard-cornix/pull/7)、`b54f1de0c93b1bfb8636251d48a45645285b29ee`。
- [main CI 33402191691](https://github.com/te9no/zmk-keyboard-cornix/actions/runs/33402191691): 全12構成成功。今回は既存artifactの書き込みであり、新たなローカルビルドは行っていない。
- 書き込んだ[IQS UF2](https://github.com/te9no/zmk-keyboard-cornix/blob/b3191a46da203c557091bb3248209f7280a07633/firmware/zmk-keyboard-cornix/main/madula_iqs.uf2): artifact commit `b3191a46da203c557091bb3248209f7280a07633`、893440 bytes。
- Git blob `72e0d5f4f2a468084ad47b1d62fda9c97ab5ed0c` と一致を確認。
- SHA256 `f0727c4d1a2b1ce2d3a3ad60cc9ba0c46efb6f91374b4264e7393b8448e8c161`。

## ツールによる実測

所有者の「IQSを書き込んで」に従い、COM454の接続先をシリアルで識別して1200 baudでブートローダーを起動。H: のディスクシリアル、XIAO-SENSEラベル、Seeed_XIAO_nRF52840_Sense board IDを照合し、IQS UF2をコピーした。他キーボードには書き込んでいない。

再起動後はCOM454（Debug）とCOM447（Studio）を115200 baudで開けることを確認。Studio core get-device-info（request ID 63）は28-byte応答を返し、Madulaの名前と対象デバイスのシリアル一致を確認した。確認後は両ポートを解放した。ソース修正・settings resetは行っていない。

これは書き込み完了、CDCポート復帰、Studio基本通信の実測であり、入力やLEDの目視確認とは区別する。

## 所有者による実機確認

上記書き込み後に「入力・方向、DYA Studio接続、LED表示」の確認を依頼し、所有者から「OKです」と返答を得た。

- IQS入力・方向: 合格。
- DYA Studio UI接続: 合格。
- 今回のLED表示（内蔵RGB/SPI LED併用・USB表示・レイヤー番号点滅）: 合格。

LEDは今回の確認項目に対する所有者申告であり、点滅タイミングなどをツールで測定したものではない。

## 全variantの集約と残件

[TB確認記録](madula-tb-orientation-validation-2026-08-31.md)、[LPPS確認記録](madula-lpps-studio-validation-2026-08-31.md)、本IQS記録で、それぞれの入力・Studio・LED表示が確認済み。これによりStudio/LED項目の `dual-led-hardware` と `usb-layer-led-hardware` を合格とする。

この初回確認時点ではLPPS/IQSの同一variantへのCDC復帰が未確認だった。後続の[IQS CDC確認](madula-iqs-cdc-recovery-2026-09-01.md)でIQSも合格し、残りはLPPSのみ。`cdc-recovery-hardware` はLPPS確認まで保留を維持する。初回のLPPS→IQS切り替えを同一variantの復帰試験へ転用していない。

別項目のIQS gesture・cold-start・長時間動作・split接続については、今回の「OKです」から合格を推定しない。

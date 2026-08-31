# Madula IQS: CDC同一firmware復帰確認（2026-09-01）

## 対象

所有者の「つづけて」に従い、接続中のMadula IQSで未確認のCDC再書き込み・復帰を実測した。対象は[前回確認済みのmain artifact](madula-iqs-studio-validation-2026-08-31.md) `b3191a46da203c557091bb3248209f7280a07633` の `madula_iqs.uf2`（893440 bytes）。ソース・設定変更、新規ビルド、他キーボードへの書き込みはない。

SHA256: `f0727c4d1a2b1ce2d3a3ad60cc9ba0c46efb6f91374b4264e7393b8448e8c161`。

## 実測結果

1. COM454のUSB親デバイスのシリアルと対象Madulaの一致を確認。COM454/COM447を115200 baudで開けることを事前確認した。
2. COM454の1200 baud/DTR・RTS操作でブートローダー起動。H: XIAO-SENSEのディスクシリアルと `Seeed_XIAO_nRF52840_Sense` board IDを照合した。
3. H: CURRENT.UF2のapplication範囲を対象IQS UF2と比較し、**1745/1745ブロック一致**。全flash・settingsのコピーは保存していない。
4. 同じSHA256のIQS UF2を再書き込みし、コピー完了を確認。
5. 復帰したCOM454/COM447をUSB親デバイスで再識別。両ポートを115200 baudで開けることを確認した。
6. Studio core get-device-info（request ID 64）で、対象Madulaの名前とシリアルを含む**28-byte応答**を照合した（2026-09-01 00:06 JST）。
7. Debugから**983文字のログ本文**を受信。LEDとBLEリンク状態のログが含まれ、ポート列挙だけでなくログ受信まで確認できた。公開記録には接続相手のアドレスを含めない。

終了時は両ポートを閉じて解放。IQSの同一firmwareへのCDCブート・再書き込み・復帰、Debugログ受信、Studio基本通信を合格とする。

## 残件

このIQS確認時点の残件はLPPS自身へのCDC再書き込み・復帰のみだった。後続の[LPPS確認](madula-lpps-cdc-recovery-2026-09-01.md)で合格し、集約ゲート `cdc-recovery-hardware` も完了。IQSのgesture・cold-start・長時間動作・split接続の追加検証は本試験の対象外であり、ログ中の接続状態だけで合格にはしない。

# Fleet整理 — 2026-10-09

## MeKaBu Studio

- 修正commit: [d49fab5](https://github.com/te9no/zmk-config-MKB2/commit/d49fab5b6738935da15ea404f6858a87f887ad30)。
- リモートzmk-0.4に含まれることをgit ancestryで確認。
- [公開リリース](https://github.com/te9no/zmk-config-MKB2/releases/tag/zmk-0.4-20261004)はdraftではなく、16 UF2・まとめZIP・SHA256SUMSを確認。
- 本会話でMeKaBuを両側TBで書き込み、その後ユーザーがマクロ・電源断後コンボの動作を確認した記録を採用。今回は再書き込み・再実験していない。
- 未コミット・未公開という旧記述を解消し、マクロ割り当てとコンボの待ちカードを削除。履歴は台帳に保持。
- Shift付きキー割り当ての報告元での再現、全moduleの実機動作、他機種への横展開は合格扱いにしない。

## LPPS静止ドリフト

|対象|統合先|変更|コードcommit|
|---|---|---|---|
|Polaris左|zmk-0.4|1000→1500|35d64dc8b7c867eaf99dfe006006f393f8b536d0|
|MKB左右|zmk-0.4|600→1500|3efccb00eec803db57dc6f79cad577465de526c1|
|Cornix/Madula|main|1200→1500|9cfab7efe910c3968f43b457104e4a4a073b6210|

4 targetのローカルビルドと生成DTSの両軸1500は前作業で確認済み。
今回リモート統合先とCI成功を確認した。新値での書き込み・静止ドリフト・微操作は未確認。
旧LPPS pinout/free XYの実機合格は変更せず、新項目で独立管理する。
公開済みMeKaBuの20261004リリースはLPPS変更より前であり、新値を含むリリースではない。

## 保留・優先度

Fleetのopen PRは確認時点で0件。SAA低優先度化のPR #104はmainへ統合済み。
SAAはlater/lowのまま維持。未確認の項目を一括で完了にはしない。
古いvariant別のpinmux、Studio診断、JOY、IQS追加検証は、今回の一般的な動作確認から推測して完了にせず残す。
ファームウェア修正・書き込み・他者へのPR操作は今回行っていない。

# Cornix / Madula IQS main通常版の実機監査（2026-08-30）

対象は `cornix` / `iqs9151-upstream-zmk-0.4` のみ。ユーザーがMadulaへIQSを接続したため、直前のTB版から既存main通常版へ切り替えた。ソース修正、マージ、他repositoryへの横展開は行っていない。

## ソース・ビルド

- [Cornix main](https://github.com/te9no/zmk-keyboard-cornix/commit/578c9f1f94c1a3d2bdd0b7c33ba2fe02c58dac72): `578c9f1f94c1a3d2bdd0b7c33ba2fe02c58dac72`
- ShiniNet本家 `zmk-driver-iqs9151` を `08a6fd19c5aa5ae7f11daf371b5a391cd8596783` に固定。ZMKはcormoran `e5c9b6915b56801193e359dd9bad4a167ce0d1b8`。
- [CI 33278783894](https://github.com/te9no/zmk-keyboard-cornix/actions/runs/33278783894): 同じmain SHA、全12 target成功。今回使用したのはjob `99170396098` / `artifact-madula_iqs`。
- CIの生成DTS・configとUF2について21項目を確認。`xiao_ble/nrf52840/zmk`、TWIM 400 kHz、SDA P1.14 / SCL P1.13 / IRQ P1.12、IQSアドレス0x56、ROTATE_270、IQS listener、USB loggingと1200-baud triggerを確認した。
- 今回はCI成果物の監査で、新たなローカルビルドは行っていない。[8月28日の通常版just.sh build](madula-iqs-validation-2026-08-28.md)とUF2ハッシュが一致した。
- 通常版は `CONFIG_INPUT_IQS9151_LOG_LEVEL=3`。製品IDの正常値と初期化完了メッセージは本家コードでDEBUGレベルのため、通常版でそのログが出ないだけでは成功・失敗を断定できない。

## 書き込み・readback

- 書き込み前はmainのTB版。Madula本体のUSB識別情報とUF2ボリュームの対応を確認して、TB版logging CDCから1200 baudでブートローダーへ移行した。
- IQS通常版 `madula_iqs.uf2` を書き込んだ。
- SHA256: `6191ba66643c7272768436b94a8df48dee56494a0342a0157823ebb2e9c3d926`
- IQS版はCOM445 / COM447として再列挙。logging / boot triggerはCOM447。TB版のCOM454とは異なる。
- IQS版COM447の1200 baudで再度ブートローダーへ移行し、readbackのアプリ領域 **1261/1261ブロック** がCI成果物と一致した。
- 確認後、同じIQS通常版を書き戻して起動状態へ復帰。設定消去は行っていない。

## 今回の起動ログと判定

初回の通常版起動で次を捕捉した。

```text
[00:00:00.830,444] <wrn> iqs9151: RDY timeout after 500ms
[00:00:00.830,718] <err> iqs9151: unexpected product number 0xeeee
```

正常な製品ID `0x09bc` と異なり、初回のセンサー初期化は失敗。書き込み後の1261ブロック一致により、別targetを書いた可能性は排除できるが、接続状態・電源状態・初期化タイミング等の原因はまだ特定していない。

readback確認後の2回目の起動では、採取した12秒間に次のRDY警告を検出した。初回と同じ製品IDエラーはこの採取範囲に出ていないが、正常な初期化完了や入力成功の証明にはしない。

```text
[00:00:01.005,065] <wrn> iqs9151: RDY timeout after 500ms
```

- ソース、CI、生成DTS、通常版flash/readback、CDC再列挙・boot trigger: 確認済み。
- 通常版の初期化・入力・方向: 下記のユーザー確認で**合格**。初回初期化失敗は観測履歴として残し、起動が常に安定するとの判定はしない。
- gestures、cold-start、長時間動作、split接続: 引き続き未確認。
- 8月28日の診断版に対する入力・方向・初期化の合格記録は履歴として保持する。今回の通常版の合格へ読み替えない。

ユーザーへ完全な電源OFF（USB切断、バッテリー使用時はスイッチOFF）後の再接続と上下左右入力の確認を依頼した。ソフトウェア再起動をcold-start合格とは数えない。

## ユーザーによる通常版の動作確認

上記確認依頼に対し、ユーザーが **「OK動きます」** と回答した。書き込んである通常版の入力・方向と、入力可能な状態への初期化を合格とする。正常製品IDや初期化完了をCDCで直接読めたという意味ではない。完全な電源OFFの実施やgesture・長時間・split接続について個別の報告はないため、それらは保留を維持する。

続けて **「診断版はもういらないよ」** と指示されたため、今後の使用・検証対象はmain通常版に統一する。診断版の追加ビルド・再flashは行わず、8月28日の診断版記録は過去の証跡としてのみ残す。

## 移行完了と追加検証の分離（2026-08-30）

ユーザーが「未確認4項目を別の追加検証として保留に残し、移行項目をクローズする」方針を承認したため、台帳のみを整理した。

- [本家ドライバ移行](../changes/iqs9151-upstream-zmk-0.4.json)のCornixは、main統合・ビルド/CI・通常版のflash/readback・CDC・入力/方向の既存証拠により完了。`merged`を保持し、未確認4項目を追加検証へ移管した。
- [Madula IQS通常版の追加実機検証](../changes/madula-iqs-additional-validation.json)へ `gestures`、`cold-start`、`long-duration`、`split-connectivity` をすべて `pending` のまま移した。合格・免除・検証不要とは判定していない。
- 次の作業は `cornix-madula-iqs-additional-validation`。通常版を対象とし、実施時のrevisionと各結果を別々に記録する。
- 上記の初回起動失敗と再起動後のRDY警告は引き続き観測履歴。原因や起動安定性は未確定。
- 今回は新しいビルド・実機検証・書き込み・ソース修正・マージを行っていない。対象はCornixのみで、他repositoryの状態は変更していない。

## 証跡の扱い

ローカルの `.zmk-workspace/evidence/cornix-madula-iqs-audit-20260830/` にCI log、生成DTS/config、UF2、照合結果、初期化に限定したログ抜粋を保存。機器の固有識別情報と生の入力ログは公開台帳に含めない。full-flash readbackは照合後に削除し、ブロック一致数だけを保持する。

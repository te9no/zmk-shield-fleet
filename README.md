# zmk-shield-fleet

共通ドライバ／ZMK module の変更を、各キーボードリポジトリへ反映したか記録する
台帳です。必要な変更が機械的に表現できる場合は、同じ台帳エントリから対象ごとの
ドラフトPRも作れます。

`fleet.toml` は管理対象リポジトリの一覧、`changes/<id>.json` は変更ごとの台帳です。
キーボード固有のシールドや設定は各リポジトリに残します。

## 台帳の流れ

1. 共通ドライバを修整し、revision／commit と変更URLを確定する。
2. `examples/change.json.disabled` を `changes/<id>.json` にコピーする。
3. 全利用リポジトリを `repositories` と `tracking` に列挙する。
4. `west.yml`、`.overlay`、`.conf` など必要な置換を `steps` に記録する。
5. planで差分を確認し、ローカル適用またはGitHub ActionsからドラフトPRを作る。
6. PR状態を同期し、手動反映分は台帳へ記録する。

`trigger` には、変更を最初に実機検証したキーボードのcommitを記録します。
`scope` を `{ "module": "iqs9151" }` または `{ "all": true }` とすると、
`fleet.toml` から対象集合を再計算し、一台でも台帳から漏れると `ledger check` が失敗します。
自動置換が安全に書けない変更は `steps: []` のチェックリスト専用台帳にできます。

```sh
shield-fleet ledger list
shield-fleet ledger show example-driver-update
shield-fleet ledger check
shield-fleet change plan example-driver-update --workspace .fleet-workspace --diff
shield-fleet ledger sync example-driver-update --write
shield-fleet ledger mark example-driver-update --repo mdk --status applied --commit <sha>
```

状態は `pending`、`pr-open`、`merged`、`applied`、`closed`、`blocked`、
`not-applicable` です。`ledger sync` は `fleet/<変更ID>` ブランチのPRを検索し、
状態とURL、merge commitを更新します。

## 修整できるファイル

台帳の `steps` はUTF-8テキストなら拡張子を限定しません。一件の変更に次をまとめられます。

- `config/west.yml` のmodule revision
- シールド／snippetの `*.overlay`
- Kconfigの `*.conf`
- devicetree binding、YAML、DTS、ヘッダなど

操作は反復可能な `literal_replace` と `regex_replace` だけです。ファイルの新規作成、
削除、任意shell実行は行いません。各stepの `expect` はリポジトリごとの
「変更前＋変更後」の期待出現数で、どれか一つでも外れると書込み前に全体を停止します。

## セットアップと監査

Python 3.11以上を使用します。実行時の外部Python依存はありません。

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
shield-fleet inventory
shield-fleet audit
shield-fleet ledger check
```

既存の開発checkoutを汚さないよう、一括修整には専用workspaceを推奨します。

```sh
shield-fleet clone --workspace .fleet-workspace --ci-only
shield-fleet audit --workspace .fleet-workspace --ci-only
```

`fleet.toml` には Polaris、MDK、MKB2、MRM、SparAkashaAnanta、Cornix、Torabo、
Berkut51、GeaconSolstice、koZakura、GeaconSparagmos、ローカル専用CaGiMeを登録しています。
CaGiMeは監査と台帳には参加できますが、GitHub remoteがないためPR rolloutからは除外されます。

## ドラフトPR rollout

Actionsの `Roll out driver change` を手動実行し、`changes/<id>.json` のIDを入力すると、
対象ごとにfresh checkout、preflight、適用を行い、変更があるリポジトリだけに
`fleet/<id>` ブランチのドラフトPRを作ります。

他リポジトリへ書き込めるfine-grained PATをrepository secret `FLEET_TOKEN` に登録します。
対象リポジトリだけを選び、ContentsとPull requestsのRead and writeを付与してください。

各キーボードのfirmware buildを確認してからmergeし、その後
`shield-fleet ledger sync <id> --write` を実行します。

## 開発時の確認

```sh
python -m unittest discover -s tests -v
python -m zmk_shield_fleet ledger check
```

旧 `campaign` コマンドは互換aliasとして残しています。

初回の横断検査結果は [`docs/cross-repo-audit-2026-08-21.md`](docs/cross-repo-audit-2026-08-21.md)
に記録しています。

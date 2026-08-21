# zmk-shield-fleet

複数の ZMK キーボードリポジトリに分散した、交換式入力モジュールの
シールド／snippet を横断保守するための補助リポジトリです。

このリポジトリはファームウェアの依存先ではありません。各キーボード固有の
ピン配置や split 経路はそれぞれのリポジトリに残し、同じ修整を行うときだけ
対象、件数、差分を一つの campaign として管理します。ランタイムで本当に共通な
ドライバや behavior は、従来どおり独立した ZMK module に置きます。

## 管理対象

`fleet.toml` が唯一の台帳です。初期状態では次を登録しています。

| ID | リポジトリ | 構成方式 | 入力モジュール |
| --- | --- | --- | --- |
| `polaris` | `te9no/zmk-config-GeaconPolaris` | module snippet | ENC, IQS, JOY, LPPS, TB, TPD |
| `mdk` | `te9no/zmk-config-MDK` | slot snippet | ENC, JOY, KEY, RZT, TB, TPD |
| `mkb2` | `te9no/zmk-config-MKB2` | module shield | ENC, JOY, KEY, LPPS, RZT, TB, TPD |
| `mrm` | `te9no/zmk-config-MRM` | slot snippet | ENC, JOY, KEY, RZT, TB, TPD |
| `saa` | `te9no/zmk-config-SparAkashaAnanta` | module shield | ENC, IQS, JOY, KEY, TB, TPD |
| `cornix` | `te9no/zmk-keyboard-cornix` | module snippet | IQS, LPPS, TB |
| `torabo` | `te9no/zmk-keyboard-torabo-tsuki-lp` | module snippet | TB, TPD |
| `cagime` | ローカルのみ | module shield | ENC, IQS, JOY, KEY, TB, TPD |

CaGiMe は現在 GitHub remote と初回 commit がないため、ローカル監査と campaign
には参加しますが、CI の clone／PR rollout からは除外しています。

## できること

- 台帳にある checkout、origin、必須ファイルの監査
- アーキテクチャと対応モジュールを一覧化
- 同一系列のディレクトリ間に生じた drift の検出
- 明示したファイルだけを対象にした literal／regex 一括置換
- 置換前と置換後の合計出現数による、適用前の件数保証
- 全対象の preflight 完了後にだけ書き込む一括適用
- GitHub Actions から対象ごとの draft PR を作る rollout

ファイルの新規作成・削除や任意 shell 実行は campaign の機能に含めていません。
構造変更が必要な場合は、まず通常の PR で共通インターフェースを整え、その後の
反復可能な置換だけを campaign にします。

## セットアップ

Python 3.11 以上だけを使用し、実行時の外部パッケージ依存はありません。

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
```

このリポジトリが既存 checkout と同じディレクトリにある場合、`fleet.toml` の
既定 workspace `..` をそのまま使えます。

```text
config/
├── zmk-shield-fleet/
├── zmk-config-GeaconPolaris/
├── zmk-config-MDK/
└── ...
```

## 棚卸しと監査

```sh
shield-fleet inventory
shield-fleet audit
```

対象を絞る例です。

```sh
shield-fleet inventory --tag mekabu
shield-fleet audit --repo mdk --repo mrm --strict
```

`audit` は dirty tree を warning として扱います。origin の不一致、必須 glob の
欠落、`enforce = true` の mirror drift は error です。`--strict` は warning も
失敗にします。

MDK と MRM の slot snippet は由来が同じため mirror として登録済みですが、現状は
既知の差分があります。初期値を `enforce = false` とし、差分解消までは warning、
解消後は `true` にして再発を CI で止められるようにしています。

## 安全な作業用 clone

既存の開発用 checkout には未コミット変更があり得ます。一括修整には別 workspace
を用意するのが基本です。

```sh
shield-fleet clone --workspace .fleet-workspace --ci-only
shield-fleet audit --workspace .fleet-workspace --ci-only
```

`clone` は存在するディレクトリを上書きしません。既定では各保守対象 branch を
depth 1 で clone します。開発中の構成だけ default branch と異なる場合は `maintenance_branch`
を使用します（現在は Cornix が該当します）。`--depth 0` で全履歴を取得できます。

## Campaign の作成と適用

`examples/campaign.json.disabled` を `campaigns/<id>.json` にコピーし、内容を
確定してから `enabled` を `true` にします。

```json
{
  "schema": 1,
  "id": "example-fix",
  "enabled": true,
  "title": "Explain the uniform fix",
  "description": "Why every target needs it",
  "repositories": ["mdk", "mrm"],
  "steps": [
    {
      "id": "replace-setting",
      "repositories": ["mdk", "mrm"],
      "paths": ["snippets/Slot*_TB/**/*.conf", "snippets/Slot*_TB/*.conf"],
      "operation": "literal_replace",
      "find": "CONFIG_EXAMPLE=old",
      "replace": "CONFIG_EXAMPLE=new",
      "expect": {
        "mdk": { "min": 1, "max": 3 },
        "mrm": { "min": 1, "max": 3 }
      }
    }
  ]
}
```

`expect` は各リポジトリで見つかる「旧表現＋新表現」の件数です。旧表現だけでなく
新表現も数えるため、途中まで適用済みの状態を検出しつつ campaign を再実行できます。
期待件数が一つでも外れると、全ファイルを未変更のまま停止します。

まず plan と diff を確認します。

```sh
shield-fleet campaign plan example-fix \
  --workspace .fleet-workspace \
  --diff
```

問題がなければ適用します。

```sh
shield-fleet campaign apply example-fix \
  --workspace .fleet-workspace \
  --diff
```

変更対象の Git working tree が dirty の場合は拒否します。既存変更との併用が本当に
必要な場合だけ `--allow-dirty` を明示してください。

正規表現を使う場合は `operation` を `regex_replace` にし、適用済み状態を数える
`already_pattern` も必ず指定します。利用できる flag は `IGNORECASE`、
`MULTILINE`、`DOTALL` です。

## GitHub Actions

`audit.yml` は test の後、CI 対象を fresh clone して台帳を監査します。

`rollout.yml` は手動実行専用です。campaign ID を指定すると、対象リポジトリごとに
fresh checkout、preflight、apply を行い、変更がある対象だけ draft PR を作ります。
fleet リポジトリ自身の `GITHUB_TOKEN` では他リポジトリに書けないため、次の権限を
持つ fine-grained PAT を repository secret `FLEET_TOKEN` に登録してください。

- 対象リポジトリだけを選択
- Contents: Read and write
- Pull requests: Read and write

rollout は常に draft PR にし、各キーボードの firmware build 結果を確認してから
merge する運用を想定しています。

## 新しいリポジトリの追加

1. `fleet.toml` に repository table を追加する。
2. `required_globs` に、その方式を識別できる必須ファイルを指定する。
3. `modules` と `tags` を登録する。
4. GitHub から clone できない対象は `ci = false` にする。
5. `shield-fleet audit` と test を実行する。

完全に同じ内容を維持するディレクトリは `[[mirrors]]` に登録できます。意図的な
差分がなくなってから `enforce = true` に切り替えてください。

## 開発時の確認

```sh
python -m unittest discover -s tests -v
python -m zmk_shield_fleet inventory
```

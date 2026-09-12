# Git管理の集約

2026-09-12のユーザー指示に基づき、取得した上流コード・自作コード・設定・文書をルートのGitで管理する構成へ変更した。
動画・重み・生の実験出力・実データはローカル管理を継続する。コードとデータの既存配置を維持し、削除していない。
以下は集約・ステージング時点の作業記録。公開状況はルートのGit履歴とGitHub側の履歴で確認する。

## 上流コードと出典

次の9個の上流ディレクトリを、入れ子のGitやsubmoduleを持たない通常のディレクトリとして扱う。

- `research/sign/LiTFic/LiTFiC`
- `research/sign/SpaMo/SpaMo`
- `research/sign/SpaMo/upstream/sign-vla`
- `research/sign/ssvp_slt/upstream`
- `research/sign/uni-sign/Uni-Sign`
- `research/vsr/auto_avsr/auto_avsr`
- `research/vsr/swinlip/SwinLip`
- `research/vsr/usr2/upstream`
- `research/vsr/vallr/VALLR`

取得元URLと元revisionは [upstream-sources.json](../research/upstream-sources.json) に保存した。
SSVP-SLT・Uni-Sign・VALLRの既存ソース変更は `research/upstream-patches/` に保存した。
これは取り込み前のソース差分で、今回のGit管理設定の変更や、今後の変更を自動追跡するものではない。
上流のLICENSE・著作権表示・READMEは保持する。今回 `.gitmodules` と `.gitattributes` の追加は不要と判断した。

## Gitメタデータの退避と復元

9個の `.git/` は削除せず、次のGit対象外ディレクトリへ移動した。

```text
.local/git-metadata-backups/20260912-233113/<元の上流ディレクトリ>/git-metadata/
```

同じ場所に、退避前のstatus、追跡ファイル一覧、完全な変更差分、追跡ファイルのSHA256も保存した。
元の `.gitignore` の一部は `original-files/` に保存している。
`.local/` にはGit設定や履歴が含まれるため、GitHubへ追加しない。

独立したGitへ戻す必要がある場合は、対象ディレクトリに新しい `.git` が存在しないことを確認した上で、
対応する `git-metadata/` を元の `.git/` へ戻す。コード・データの置換や `git reset --hard` は不要。
現在のルート集約方針では、モデル内の `.git` を復元しない。

## 除外するもの

- モデル内の `weights/`、`checkpoints/`、`outputs/`、仮想環境、キャッシュ、生ログ。
- 動画・音声・モデルバイナリ・顔ランドマーク。上流に同梱されたものも対象。
- Uni-Signの学習用ラベル、Auto-AVSRの学習用原稿・入力ID一覧、実演映像。
- 評価用の `data/`。例外として保存方針READMEと従来のVSR撮影用 `script.txt` を管理する。

モデル実装の `data/`・`dataset/` にはPythonコードもあるため、名前だけで一括除外しない。
文書の構成図・グラフ、語彙定義、テスト用の小さなテキストfixtureは管理対象に残す。
上流の一部 `.gitignore` にあったJSON・TOML・Python・notebook等の一括除外は調整した。
取り込むAuto-AVSRのnotebook 3本に保存済み出力・添付画像がないことを確認した。

上流で追跡されていた除外資材のパス・元revision・サイズ・SHA256は
[upstream-local-assets.json](../research/upstream-local-assets.json) に記録する。
この作業場所には実体が残るが、今後ルートリポジトリだけをcloneした環境には含まれない。
例えば `face_landmarker.task`、`20words_mean_face.npy`、SentencePieceの `.model` は推論に必要な場合がある。
別環境では、記録された元revisionの上流から必要な資材を元のパスへ取得し、SHA256を照合する。
追加取得した大きな重み・環境の準備は各モデルのREADME・`artifacts.sha256` を参照する。

## 推論時の出典記録

7本の推論・評価補助から、clone先の `git rev-parse`・`git diff`・`git status` への依存を取り除いた。
`research/source_provenance.py` が保存済みmanifestを読み、`upstream_revision` に上流の元revisionを返す。
ルートリポジトリのrevisionを上流revisionと誤認しない。未知の上流はエラーにする。

Uni-Signの `upstream_local_patch` は `upstream_local_patch_at_import` へ変更し、取り込み時の差分であることを明示した。
SSVP-SLTの `upstream_status` は `upstream_source_at_import` へ変更した。
過去の出力ファイルは変更していない。今後のコード変更はルートのGitで確認する。

出典参照の確認コマンド：

```bash
python3 -B -m unittest discover -s research/tests -p 'test_source_provenance.py'
```

## ルートのGitについて

初回の集約作業時、ルート `.git/` は空だった。
2026-09-13の追加作業で、GitHubの既存リポジトリ `https://github.com/Qutalize/openAI_hackathon.git` から履歴を取得し、ルート `.git/` に配置した。
新しい履歴は作らず、既存の `main` / `origin/main` のコミット `642f9de031fd4916503dd76b679b56f8cf69ac68` を引き継いだ。
新規2,060件・変更23件をステージングし、削除・除外対象・gitlinkの混入がないことを確認した。
このステージング確認時点ではコミット・プッシュは未実施だった。取得に使った予備コピーは `.local/root-history-20260912/` にあり、Git対象外。
共有ディレクトリの所有者が実行ユーザーと異なるため、通常のGit操作にはこのパスだけを `safe.directory` に登録する必要がある。
既存の履歴がある取り込み先では、すでに追跡済みのファイルには `.gitignore` が効かないため、indexの確認も必要。

Git管理集約の検証にモデル推論は含めない。出典参照・CLI入口・除外規則・ファイル保持を確認する。

## 実施した確認

- `.git` の退避前後で、19,334ファイルのinode・サイズ・更新時刻が一致した。
- 出典参照の単体テスト3件と、変更したCLI 7本の `--help` が成功した。CLIは `/tmp` を作業ディレクトリとしても起動した。
- 一時リポジトリで管理対象27件・除外対象77件を確認し、全件が想定どおりだった。
- 一時indexへの登録候補は2,106ファイルで、入れ子のGitを示すgitlinkは0件だった。
- 元の上流で追跡されていたコード・設定・文書に、意図しない除外はなかった。
- 推論補助の変更は出典参照とメタデータ記録に限定し、GPU推論は再実行していない。

上記は初回集約時の確認で、一時リポジトリのindexで登録を試した。
初回の詳細なローカル検証記録は `.local/git-metadata-backups/20260912-233113/validation.json` に保存した。
その後、上の「ルートのGitについて」に記載したとおり、既存のGitHub履歴を引き継いでルートのindexにも登録した。

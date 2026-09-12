# 4人のモデル検証タスクとGit運用

## 担当案

A/B/C/Dは仮名。VSRの2候補を分担し、手話調査と共通評価を並行して進める。

| 担当 | 作業場所 | 最初の成果物 |
|---|---|---|
| A：VALLR | research/vsr/vallr | 動画1本の出力、文章復元/promptの確認、所感 |
| B：LipCoordNet | research/vsr/lipcoordnet | 動画1本の出力、landmark前処理、所感 |
| C：手話 | research/sign | 言語と候補を選び、重み取得・単体推論・所感 |
| D：環境・評価 | data、共通文書、比較表 | 機材確認、共通入力の準備、再現確認、比較要約 |

モデル固有のスクリプト・設定・実験記録は各候補内に置く。UI/APIの担当は今は設けない。
共有GPUが1台なら推論時間を調整し、同時ロードによるOOMをモデルの欠陥と混同しない。

## 作業順と判断点

1. 機材・データの有無、手話言語を確認する。
2. A/B/Cは候補の入手性と環境を確認し、まず1本の推論を試す。Dは共通入力を準備する。
3. 初回の検証枠を目安2時間とし、動いた範囲と詰まった原因を共有する。時間だけで不採用にせず、修正見込みを判断する。
4. 生出力と所感を共有し、再現できた候補へ同じ自前動画を入力する。
5. Dまたは別メンバーが再現手順を確認し、比較表を更新する。
6. 採用/保留/不採用と根拠を残す。インターフェースの設計はその後の別タスクにする。

## Git運用

管理リポジトリは [Qutalize/openAI_hackathon](https://github.com/Qutalize/openAI_hackathon)。
共有作業場所の `.git/` が有効なGitメタデータでない環境では、書き込み可能な別ディレクトリへcloneして作業する。

通常の書き込み可能な開発環境で、別のディレクトリへcloneする：

```bash
git clone https://github.com/Qutalize/openAI_hackathon.git openAI_hackathon
cd openAI_hackathon
git switch -c docs/project-foundation
```

この作業フォルダのREADME、AGENTS.md、docs、自作コードと上流コードをclone先へ取り込む。
`.git/`、`.agents/`、`.codex/`、`.local/`、動画・重み・生出力はコピーしない。既存ファイルがあればdiffを見て統合する。
秘密・映像・重みが含まれないことを確認して必要ファイルを明示的にstageし、PRにする。
撮影データ、重み、実行出力、秘密情報は `.gitignore` で除外し、誤ってstageされていないことをcommit前に確認する。
上流コード・設定・文書はルートのGitで通常のファイルとして管理し、モデル内に独立した `.git` を作らない。
取得元・元revision・取り込み時の差分は `research/upstream-sources.json` に残す。
取り込み手順・退避先・除外した上流資材は [Git管理の集約](07-git-consolidation.md) を参照する。

ブランチ例：`research/vallr`、`research/lipcoordnet`、`research/sign-models`、`research/evaluation`。
mainには再現手順と実行状態を正確に残す。共有ファイルの競合はDを窓口として解消し、モデル別環境のlockfileを分ける。
PRには「何が動くか」「確認方法」「未達/制約」を記載。大きな統合PRより小さい動作単位を使う。

## 記録

各候補の `reports/<date>-<run_id>.md` に [テンプレート](../research/templates/REPORT_TEMPLATE.md) をコピーする。
成功例だけでなく、導入にかかった手間、失敗出力、利用できる場面と難しい場面を残す。
Codexへの依頼、生成/修正箇所、人の判断と再現確認を短く記録する。

| 判断 | 理由 | 状態 |
|---|---|---|
| VSR・手話の選定と試運転を先行 | 最新のユーザー指示 | 現在の方針 |
| research配下を固定し候補別に環境分離 | 将来のアプリ追加で検証を移動しないため | 採用 |
| UI/APIのディレクトリ・詳細設計を削除 | 必要になる時点で追加するため | 実施 |

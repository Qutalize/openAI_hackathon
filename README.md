# 無音声認識 is all you need

音声認識の次を作る ― 音を使わないコミュニケーションインターフェース。
チーム「ひとくち」／4人。

**現在はVSR（Visual Speech Recognition／読唇）と手話モデルの選定・試運転に集中します。**
既存モデルを取得し、動画で実際に推論して、出力・速度・導入の難しさ・所感を残します。
VALLRは公開LRS3サンプル1本でV1のCPU推論を確認し、未後処理の音素クラス列まで出力しました。文章復元・認識精度は未確認です。他候補は引き続き試運転前です。

## 作業場所

- [VSR](research/vsr/README.md)：[VALLR](research/vsr/vallr/README.md)、[LipCoordNet](research/vsr/lipcoordnet/README.md)を個別に検証。
- [手話](research/sign/README.md)：対象言語と候補を確認し、試すモデルごとにディレクトリを追加。
- [実験記録テンプレート](research/templates/REPORT_TEMPLATE.md)：まず1本の実行結果と所感を記録。
- [評価用データ](data/README.md)：映像等はローカル管理。

## 方針・運用

1. [モデル選定の進め方](docs/01-project-plan.md)
2. [ディレクトリ構成と将来の拡張](docs/02-architecture.md)
3. [モデル調査と評価方法](docs/04-model-research.md)
4. [4人の分担とGit運用](docs/06-team-workflow.md)

エージェント向け指示は [AGENTS.md](AGENTS.md)。[当初の仕様書](docs/無音声認識_is_all_you_need_仕様書.md)は将来の構想として保存しています。
会議UI、API、字幕共有は後の段階で設計します。必要になった時点で別ディレクトリに追加し、`research/` の配置と単体実行手順を維持します。

管理リポジトリ：[Qutalize/openAI_hackathon](https://github.com/Qutalize/openAI_hackathon)。

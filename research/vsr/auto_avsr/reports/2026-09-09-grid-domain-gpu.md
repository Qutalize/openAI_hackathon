# Auto-AVSR：別ドメインの英語動画（GRID）でGPU検証

2026-09-08深夜〜09日未明（JST）、ユーザー依頼によりCodex実施。
**公式公開の英語動画2本でGPU推論成功。公式正解文に対する合計WERは50%（6/12語）、文完全一致は0/2本。**

## 別ドメインと判断した根拠

使用重みは前回と同じ `vsr_trlrs2lrs3vox2avsp_base.pth`。
[上流README](https://github.com/mpc001/auto_avsr)の学習元はLRS2、LRS3、VoxCeleb2、AVSpeech。
[Auto-AVSR論文](https://arxiv.org/html/2303.14307)では、LRS2はBBC番組、LRS3はTED講演、追加データはVoxCeleb2とAVSpeechの英語動画で、LRWでのフロントエンド事前学習も記載されている。

今回は[Sheffield大学のGRID公式配布ページ](https://spandh.dcs.shef.ac.uk/gridcorpus/)から、男性・女性各1本の高画質サンプルと単語alignmentを取得した。
GRIDは固定した文型の英語短文を読む収録コーパスであり、講演・放送・YouTube由来の自然発話と、撮影場面・文の分布が異なる。
例文は命令・色・前置詞・英字・数字・副詞の6語。母語属性を各話者について独立に確認したわけではないため、「英語話者」として扱う。

GRIDは上記の公表学習元に含まれない。ただし、個々の学習動画一覧との重複照合やネット上の転載まで追跡しておらず、完全な未学習を保証するものではない。
今回の結果は、日常会話全般への汎化や、ドメイン差だけの因果効果を測る実験ではない。

## 認識結果

| 公式サンプル | 正解 | モデルの生出力 | WER |
|---|---|---|---:|
| id2 / 男性 | SET WHITE WITH P TWO SOON | SUNWIDE WOULD BE TOO SOON | 83.33%（5/6） |
| id23 / 女性 | PLACE RED IN A ZERO NOW | PLACE RED AND A ZERO NOW | 16.67%（1/6） |

正解は公式の [swwp2s.align](https://spandh.dcs.shef.ac.uk/gridcorpus/examples/swwp2s.align) と [priazn.align](https://spandh.dcs.shef.ac.uk/gridcorpus/examples/priazn.align) から `sil` を除いて生成。
正解文は推論完了後に比較のため読み込み、モデルには一切入力していない。
大文字化、英単語と語内apostropheを保持、句読点無視の単語編集距離で計算。
`TWO` と `TOO` は別単語、`SUNWIDE` は1語のまま採点し、都合のよい分割・同音語補正は行っていない。
男性例の最短編集経路は置換4＋削除1、女性例は `IN` → `AND` の置換1。
信頼度の確率は上流未提供（null）。独自の文章補正・翻訳・語彙制限なし。

## GPU・速度・前処理

| サンプル | 入力秒数 | 顔検出 | 推論秒数 | 処理合計秒数 | ピークGPU割当MiB | ピーク予約MiB |
|---|---:|---:|---:|---:|---:|---:|
| id2 | 3.00 | 75/75 | 0.862 | 9.430 | 1134.28 | 1234 |
| id23 | 3.00 | 75/75 | 0.609 | 7.230 | 1111.45 | 1236 |

GPUはRTX A6000、モデルと入力テンソルの `cuda:0` をassert済み。uv専用環境、torch 2.5.1+cu124、CUDA 12.4。
顔検出と位置合わせはCPUのMediaPipe 0.10.21。重み・上流revision・全依存は[最初の試運転](2026-09-08-gpu-smoke.md)と同一。
上流 `ModelModule`、beam size 40、CTC weight 0.1、外部LMなし。上流コード変更なし。

取得したMPEG原本は音声付き720×576、25 fps、sample aspect ratio 1。原本を保持し、映像ストリームのみH.264（CRF18、preset fast）へ変換、音声を除去した。FPS・解像度・画角を変更せず、時間切り出しもなし。
コンテナの原本duration表示は2.98秒だが、全75フレームを25 fpsで入力した時間は3.00秒。
上流の平均顔への位置合わせ、96×96口領域crop、88×88中心crop、グレースケール、平均0.421・標準偏差0.165の正規化を適用。
確認用crop動画の各35番フレームを目視し、口元が含まれることを確認。ただし全フレームのcrop品質を人手検査したわけではない。

推論時間はCUDA同期付きの単調時計測定。処理合計はimport・動画読込・顔検出・crop保存・重みロード・GPU転送・推論を含む。
事前の動画変換・Python起動前・結果保存・入力ハッシュ計算を含まない。各動画は新規プロセスで1回ずつ、OSキャッシュ等は制御していない。
VRAMはPyTorch allocatorのピークであり、ドライバ等を含む総使用量とは異なる。

## 所感

- 実行成否：2本とも終了コード0。顔検出・口領域生成・GPU推論・英語文章出力まで成功。
- 正しさ：女性例はほぼ一致した一方、男性例は大きく取り違えた。英語話者の整った短動画でも、安定して正確に読めるとは確認できなかった。
- 主観的所感：GRIDの英字・数字を含む定型文を、モデルが別の単語列として出す現象が見える。視覚的曖昧さと学習した言語分布の影響が考えられるが、原因は切り分けていない。
- 限界：公式が例示した2本のみでランダム抽出ではない。性別による性能差、GRID全体の精度、自然会話の精度は判断できない。自前動画の56.32%は未検証原稿との比較だったため、今回の公式正解との50%と直接優劣比較しない。

## 取得元・保存先・再実行

公式配布元は研究利用で自由に取得可能と明記している。原本・音声・前処理動画・生出力はローカルのGit対象外領域へ保存し、再配布していない。

- [男性の高画質原本](https://spandh.dcs.shef.ac.uk/gridcorpus/examples/id2_6000_swwp2s.mpg)：2,453,504 bytes。
- [女性の高画質原本](https://spandh.dcs.shef.ac.uk/gridcorpus/examples/id23_6000_priazn.mpg)：2,457,600 bytes。
- `outputs/grid-domain-gpu/manifest.json`：取得URL、原本・正解・モデル入力のSHA256、実行コマンド、終了コード、結果。
- `outputs/grid-domain-gpu/artifacts.sha256`：取得物・無音声入力のチェックサム。
- `outputs/grid-domain-gpu/evaluation.json`：正解と予測、編集操作列、WER、時間、VRAM。
- `outputs/grid-domain-gpu/<サンプルID>/run/`：`transcript.txt`、`result.json`、`mouth_crop.mp4`、確認用フレーム。
- `outputs/grid-domain-gpu/run.py` / `score.py`：今回の実行・採点コード。ダウンロード済みデータを使用。

指定の上流ディレクトリ `research/vsr/auto_avsr/auto_avsr/` から再実行する例。未作成の出力先を指定する。

```bash
bash ../scripts/run_vsr.sh \
  ../outputs/grid-domain-gpu/id23_6000_priazn/video_only.mp4 \
  ../outputs/grid-female-repeat
```

取得時はサンドボックス内DNSが失敗し、承認済み制限外実行で取得とGPU推論を行った。

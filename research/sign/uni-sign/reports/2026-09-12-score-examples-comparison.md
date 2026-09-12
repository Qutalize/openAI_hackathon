# How2Sign評価例・自前ASLの同一指標比較

2026-09-12。保存済みの未補正英文をCPUで再採点した。追加推論・学習・LLM補正なし。

## 数値の意味

前回示した14.96 / 12.83はBLEU-4、29.98 / 29.64はROUGE-Lであり、AccuracyやWERではない。

- **BLEU-4（0–100、高い方が良い）**：予測とGTの1～4語の連続列の一致を、短すぎる出力へのペナルティも含めて集計する。14.96は「14.96%の動画が正解」という意味ではない。今回の上流実装は13a tokenizer、case mixed、exp smoothing。`external_metrics/sacrebleu.py:1860–1875`では一致数0にも平滑化を入れるため、意味が不一致でも小さな正の値が出る。
- **ROUGE-L（今回はF値×100、高い方が良い）**：GTと予測の語順を保った共通語列を基に、一致の割合とGTのカバー率を組み合わせる。各文のF値を平均。意味を直接判定する正答率ではない。
- **WER（%、低い方が良い）**：今回は追加の参考指標。`(置換＋削除＋挿入の最小総数) / GTの総単語数 ×100`。余計な単語が多いと100%を超える。翻訳では妥当な言い換えにも誤りを付けるため、主指標や意味正解率として扱わない。
- **文字列完全一致率**：今回の予測では評価用0/12、自前0/2。正しい言い換えも不一致になるので、意味が正しい文の割合とは異なる。

WERは一様コストの単語Levenshtein距離で計算し、小文字化・句読点除去、単語内のapostropheは保持する。上流にある独自重み付きWER関数は使っていない。BLEU/ROUGEにはその小文字化を適用せず、前回と同じ上流関数 `SLRT_metrics.translation_performance` を使用した。

## 同じ採点方法での比較

| 対象 | 件数 | BLEU-1 | BLEU-4 ↑ | ROUGE-L ↑ | 参考WER ↓ | 単語編集数/GT単語数 |
|---|---:|---:|---:|---:|---:|---:|
| How2Sign・作者配布pose | 12 | 35.53 | 14.96 | 29.98 | 88.59% | 163/184 |
| How2Sign・動画からpose再抽出 | 12 | 35.53 | 12.83 | 29.64 | 95.65% | 176/184 |
| 自前ASL・動画からpose抽出 | 2 | 9.52 | 2.35 | 5.56 | 170.00% | 17/10 |

自前は最初に保存したGPU結果を使用する。後のFP32・静止・ゼロ等の対照実験から都合のよい文を選んでいない。GTはユーザー確認済みの現 `script.txt`。

| 自前入力 | BLEU-4 ↑ | ROUGE-L ↑ | 参考WER ↓ | 編集数/GT単語数 |
|---|---:|---:|---:|---:|
| `01_whats_your_name` | 2.38 | 0.00 | 266.67% | 8/3 |
| `02_greetings` | 4.03 | 11.11 | 128.57% | 9/7 |
| 2本をまとめて採点 | 2.35 | 5.56 | 170.00% | 17/10 |

BLEUの集合値は文ごとのBLEUの平均ではない。特に短い2文では平滑化や語数の影響が強く、1本目のBLEUが2.38でも内容が合っている証拠にはならない。12件と2件は異なる少数集合なので、この差から一般的な性能低下率を推定しない。

## GTと予測の例

以下のHow2Sign予測は、自前と同じ「動画→公開デモのpose抽出→英文生成」経路。成功に近い例、意味を落とす例、誤訳例を説明用に事後選択した。12件の採点対象自体は予測を見る前に固定済み。

| How2Sign test ID | GT | 予測 | 解釈 |
|---|---|---|---|
| `g3X3XE6M2_A_15-3` | Good forward extension. | It's a good forward extension. | 主旨は一致。文字列完全一致ではない |
| `g0iNy-yPisM_17-8` | I'm going to do, Save Changes, and then we're done. | And that's it. | 終了の意味だけ残り、変更を保存する操作が欠落 |
| `FZCF7kPIyOk_10-1` | This script is bound with the long bindings right there. | You'll notice that it's a little bit smaller. | 台本と綴じ具の説明が、大きさの説明へ変わる |

GTは[Uni-Sign同梱How2Sign testラベル](https://github.com/ZechengLi19/Uni-Sign/blob/eed438bcb49e30405cd6ccdfcccca330c134e830/data/How2Sign/labels.test)と公式ラベルで一致確認済み。予測は今回の保存結果から無修正で抜粋。IDの末尾 `-rgb_front.mp4` は省略した。

自前の採点対象は次の2組。

| 入力 | GT | 予測 |
|---|---|---|
| `01` | What's your name? | We're going to choose a smaller weight strainer. |
| `02` | Nice to meet you. How are you? | There's a nice little note cards that you can play with. |

## How2Signと自前入力の違い

| 観点 | 今回取得したHow2Sign 12組 | 自前2本 | 原因として言える範囲 |
|---|---|---|---|
| 対象言語 | ASL→英文 | ユーザー確認済みASL→英文 | 言語の取り違えを主要因とはしない |
| 内容 | 手順説明・道具・操作など | 名前の質問・挨拶 | How2Sign学習時の話題との適合性に差がある |
| 画角 | 人物中心、幅310–572×高さ510–614、縦長が中心 | 1920×1080の横長、PC内側カメラ | 被写体の占有率と縦横比が違う。高解像度だけで姿勢精度が良くなるとは限らない |
| 区間 | 作者配布文単位clip、poseと実フレーム数一致。公式realigned時刻の長さと整合 | 自前clip、安静時や手が下端外の区間を含む | 自前の区間境界がモデルに最適かは未確認 |
| 長さ/fps | 1.17～11.71秒、24/30fps | 約4.00/5.11秒、約30fps | 自前より短い評価例もある。短さだけが原因ではない |
| 入力上限 | 長い3本は256framesへ間引き、2経路で同じindex | 121/155frames、間引きなし | 自前の失敗は256上限による情報欠落ではない |
| 姿勢抽出 | 作者配布MMPoseのposeと、公開デモでの再抽出を比較 | 公開デモで抽出 | 公開デモ同士の比較でも自前スコアは低い。抽出器名の違いだけでは説明できない |
| 表現者・撮影条件 | How2Sign収録者と収録条件 | 自前の表現者・カメラ・照明 | 表現差の影響量、ASL表現の正確さの独立評価は未実施 |

How2Signの手順説明・収録条件の出典は[公式資料](https://how2sign.github.io/)。今回の画像寸法・fps・系列長はダウンロードしたファイルからCPU計測した。自前のブレ・重なり・画外の手については前回の骨格確認記録を参照する。

**今回のモデルは評価分布でも重要語の誤認や省略が多い。自前では話題・画角・表現などの差がさらに加わっている可能性があるが、各差の因果的な寄与はまだ測定していない。** 実装の重大な取り違えの疑いは弱まった一方、コード・推論方法に問題が一切ないことを証明したわけではない。

## 再現と保存先

プロジェクトルートから、実行済みのCPU採点コマンド：

```bash
conda run --no-capture-output -n Uni-Sign python -B \
  research/sign/uni-sign/scripts/score_saved_results.py \
  --benchmark-results research/sign/uni-sign/Uni-Sign/outputs/20260912-how2sign-benchmark-evaluation-r1/results.json \
  --output-dir research/sign/uni-sign/Uni-Sign/outputs/20260912-how2sign-self-score-comparison-r1
```

再実行では新規output-dirへ変更する。既存保存先を上書きしない。

- 生結果：`Uni-Sign/outputs/20260912-how2sign-self-score-comparison-r1/scores.json`。各指標、単語編集数、元結果パスとハッシュ、GT、予測、例を保存。
- 新規コード：`scripts/score_saved_results.py`。既存結果の採点のみ。上流BLEU/ROUGEを再利用し、参考WERを標準的な一様コストで追加。
- 新規報告：本ファイル。READMEにリンク追加。
- 元の推論結果・正解ラベル・動画・重み・依存は変更していない。

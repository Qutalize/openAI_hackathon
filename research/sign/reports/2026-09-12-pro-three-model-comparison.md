# 追加ASL動画07・08：3モデルの精度・処理時間・GPU使用量

2026-09-12。同じ原動画2本をUni-Sign、SpaMo、SSVP-SLTで直列推論した。**今回の2本ではUni-Signが原稿に最も近く、処理時間も最短だった。ただし名前の誤認などが残り、正確な翻訳には至らない。GPUメモリの観測ピークはSpaMoが最小だった。** 全6件で英文生成・計測が成功した。

## 比較結果

入力はユーザー確認済みASL、出力は英語。各動画1回、各回で新規プロセスを起動した。学習・文章補正は行っていない。

| モデル／今回の経路 | BLEU-4 ↑ | ROUGE-L ↑ | 参考WER ↓ | CLI時間平均／本 ↓ | GPUメモリ観測ピーク ↓ | GPU平均使用率 |
|---|---:|---:|---:|---:|---:|---:|
| Uni-Sign／How2Sign pose-only | **22.59** | **28.57** | **71.43%** | **15.21秒** | 13.17 GiB | 17.25% |
| SpaMo／第三者提供Sign-VLA How2Sign版 | 2.23 | 0.00 | 185.71% | 42.23秒 | **6.58 GiB** | 18.41% |
| SSVP-SLT／SONAR ASL版 | 7.05 | 0.00 | 100.00% | 164.68秒 | 8.07 GiB | 0.45% |

文字列完全一致は全モデル0/2本。BLEU/ROUGEは正答率ではなく、WERも意味の誤り率ではない。特にSSVPのBLEUがSpaMoより高いことだけで、意味がより正しいとは判断できない。

時間は**CLI起動から終了検出まで**で、import、モデル読込、動画前処理、英文生成、ハッシュ確認・記録処理を含む。常駐モデルの推論時間ではない。各モデルの既存パイプラインを比較し、OSファイルキャッシュは消去していない。2本の平均で、同じ動画の反復平均やp95ではない。

GPUメモリは同じRTX A6000上の`nvidia-smi`によるdevice全体の標本化ピークで、2本の最大値。GiB=MiB÷1024。GPU平均使用率はCLI時間で加重し、CPU処理・モデル読込・記録時間も含む。使用率の低さを処理の速さや効率の良さとは解釈しない。

## 原稿と出力英文

参照は各入力ディレクトリの`script.txt`。07は`What's your name?`、08は`I am named <参照名>.`という自己紹介。参照名はこの要約では伏せ、原稿全文はローカルの[共通採点JSON](../outputs/20260912-pro-comparison-r1/comparison.json)に保存した。下表のモデル出力は未補正。

| モデル | 動画07の出力 | 動画08の出力 |
|---|---|---|
| Uni-Sign | What's your name like? | My name is Sedrick. |
| SpaMo | one, two, three, four. | hi, i'm robert todd and thank you for watching. |
| SSVP-SLT | Yes. Very. | We are 6.6. |

同じ基準で文章の意味を比較した。07は「相手の名前を尋ねる意図」と「余分な限定や別の問いがないこと」、08は「自己紹介の意図」と「参照名の保持」を見る。

- **Uni-Sign**：07は名前の質問に近いが、余分な`like`で「どんな名前か」というニュアンスへ変わる。08の`My name is`は妥当な言い換えだが、名前が違う。発話意図は2本とも近いものの、正確な翻訳とはしない。
- **SpaMo**：07は質問と無関係な数字列。08は自己紹介の形が部分的に近いが、名前を誤認し、原稿にない挨拶や視聴への謝辞を追加する。
- **SSVP-SLT**：07は短い肯定の返事、08は数字を含む別内容で、どちらも原稿の意図・重要情報を伝えていない。

意味評価は提供原稿と英文の比較であり、ASL話者による動画の独立再注釈ではない。Uni-Signの今回の2出力は、前回の[07・08評価](../uni-sign/reports/2026-09-12-self-07-08-pro-evaluation.md)と一致した。追加の反復安定性評価や、一般的なモデルの優劣を示す大規模評価ではない。

### 文別スコア

| モデル | 動画 | BLEU-4 | ROUGE-L | WER | 単語編集数／原稿語数 |
|---|---|---:|---:|---:|---:|
| Uni-Sign | 07 | 42.73 | 57.14 | 33.33% | 1/3 |
| Uni-Sign | 08 | 10.68 | 0.00 | 100.00% | 4/4 |
| SpaMo | 07 | 2.76 | 0.00 | 133.33% | 4/3 |
| SpaMo | 08 | 3.75 | 0.00 | 225.00% | 9/4 |
| SSVP-SLT | 07 | 7.99 | 0.00 | 100.00% | 3/3 |
| SSVP-SLT | 08 | 12.44 | 0.00 | 100.00% | 4/4 |

全モデルを既存Uni-Signの同じ`score_saved_results.score`で採点した。BLEUは上流corpus BLEU（13a、大小文字区別、exponential smoothing）、ROUGEは上流`rouge`のROUGE-L F値平均×100。集計BLEUは文別値の平均ではない。旧SpaMo報告のstemmed `rouge-score`値は混ぜていない。

WERは小文字化・句読点除去・語中apostrophe保持の最小単語編集距離÷原稿語数×100。余計な語が多いと100%を超える。08のUni-Signでは文面の4語すべてが異なるため100%だが、自己紹介の言い換えまで意味が誤りということではない。短文では平滑化・句読点の影響が大きく、意味が不一致でもBLEUは正になり得る。翻訳信頼度はどのモデルも提供せず、値は作成していない。

## 処理時間の内訳

| モデル | 動画 | 外部CLI全体 | モデル読込 | 前処理・視覚処理 | 翻訳段階 |
|---|---|---:|---:|---:|---:|
| Uni-Sign | 07 | 15.41秒 | 5.49秒 | 2.93秒 | 0.391秒 |
| Uni-Sign | 08 | 15.01秒 | 5.47秒 | 3.12秒 | 0.482秒 |
| SpaMo | 07 | 46.25秒 | 8.12秒 | 23.47秒 | 0.268秒 |
| SpaMo | 08 | 38.22秒 | 6.51秒 | 23.48秒 | 0.610秒 |
| SSVP-SLT | 07 | 148.29秒 | 20.84秒 | 前処理109.30秒＋特徴抽出0.492秒 | 0.141秒 |
| SSVP-SLT | 08 | 181.08秒 | 18.70秒 | 前処理146.62秒＋特徴抽出0.486秒 | 0.175秒 |

工程の境界はモデル間で異なるため、内訳の列をそのまま同じ演算の比較に使わない。内訳の合計とCLI全体の差にはimport・記録処理などが含まれる。

- Uni-Signの前処理はpose抽出器の初期化、姿勢推定、pose保存/hash、正規化を含む。翻訳段階はpose encoderのforwardと英文生成を含み、前後にCUDA同期あり。
- SpaMoの視覚処理はCLIP/VideoMAEの読込・抽出・解放を含む。モデル読込列は翻訳モデルだけ。動画デコード・中央cropはこの視覚処理時間の区間外。各工程末尾にCUDA同期あり。
- SSVPの内部値は上流`time.time()`でCUDA同期を追加しない参考値。**顔検出だけで07は109.049秒、08は146.066秒**かかり、現構成の待ち時間の主因だった。CPU版dlibを使用し、検出前の縮小は既定のfalse。最適化した場合の速度・出力は今回測っていない。

## GPU計測

| モデル | 動画 | deviceピーク GiB | 開始時との差 GiB | 対象プロセス群ピーク GiB | 平均使用率 | 使用率ピーク |
|---|---|---:|---:|---:|---:|---:|
| Uni-Sign | 07 | 13.169 | 13.148 | 13.143 | 21.14% | 93% |
| Uni-Sign | 08 | 13.165 | 13.145 | 13.139 | 13.25% | 96% |
| SpaMo | 07 | 6.435 | 6.414 | 6.408 | 11.12% | 100% |
| SpaMo | 08 | 6.577 | 6.557 | 6.551 | 27.24% | 100% |
| SSVP-SLT | 07 | 8.048 | 8.027 | 8.021 | 0.56% | 50% |
| SSVP-SLT | 08 | 8.065 | 8.045 | 8.039 | 0.37% | 66% |

GPUはRTX A6000、容量49,140 MiB。全6件の開始時は21 MiB、既存compute processなし。同時GPU推論なし、無関係compute PIDなし、監視エラーなし。終了後も21 MiB・使用率0%へ戻った。

目標0.2秒間隔、計2,220標本。実際の最大間隔は全6件で0.284秒以下。deviceメモリ・使用率とcomputeプロセス一覧は順次照会するため厳密な同時刻値ではない。短い瞬間ピークを取りこぼし得るので、必要VRAMの厳密な下限や安全な収容台数を保証しない。開始時との差も参考値。

対象プロセス群には各CLIと観測された子プロセスを含む。SpaMo内部のPyTorch allocated peak（07: 5.487 GiB、08: 5.559 GiB）は計測範囲が異なるため主表へ混在させない。SSVPはCPU顔検出中もGPUにモデルを保持するため、低使用率でもメモリは消費する。

## 入力とモデル構成

| 動画ID | 元ファイル | 解像度 | fps | フレーム | 長さ |
|---|---|---|---:|---:|---:|
| 07_whats_your_name_pro | whatisyourname.mp4 | 1280×720 | 29.970 | 90 | 3.003秒 |
| 08_greetings_pro | mynameis (2).mp4 | 1280×720 | 29.970 | 119 | 3.971秒 |

`data/sign/<ID>/`の同じ原動画を使用し、全モデルの入力SHA256が現在の実ファイルと一致することを検証。モデルごとの既存前処理・生成設定は維持したため、同じ前処理や同じbeam数によるアーキテクチャ単独の比較ではない。

| モデル | 使用重み・上流revision | 主な経路・設定 |
|---|---|---|
| Uni-Sign | How2Sign pose-only、`eed438bcb49e30405cd6ccdfcccca330c134e830` | RTMLib Wholebody→部位別正規化→英文。全90/119フレーム使用、BF16、beam4、seed42 |
| SpaMo | 第三者Sign-VLA How2Sign版、`d34bc0b62927a5b1b1b3f4fefcc0828c3f0b9983` | 中央crop 210:260→210×260、CLIP S²＋VideoMAE→Flan-T5。beam5、samplingなし、seed0、ICLなし |
| SSVP-SLT | 公開SONAR ASL版、`7ed332b0db35884a36b73019ca29bf0755537def` | dlib顔検出→人物crop/224×224/時間sampling→SignHiera→SONAR。Daily Moth向け調整済み経路、既定設定 |

SpaMoの今回の重みは原著者公式How2Sign版と確認されたものではなく、配布者がASL/How2Sign学習済みと説明する第三者版。SSVPはSONAR公開デモの構成で、論文のHow2Sign評価経路と同一ではない。比較対象はこの環境で再現済みの各推論経路であり、論文性能の順位ではない。

音声・参照原稿をモデル文脈へ渡さない。Uni-Sign補助内の原稿読み込みは生成終了後の採点用のみ。映像の外部送信なし。環境はモデル別に分離し、依存や重み・上流コードは変更していない。revision、重みSHA256、実コマンド、環境は各モデルの生記録・個別報告に保存した。

## 再現・成果物・検証

プロジェクトルートで実行したコマンド。再実行時は未使用の`--run-name`と出力JSON名を指定する。

```bash
python3 -B research/sign/scripts/benchmark_pro_videos.py \
  --run-name 20260912-pro-comparison-r1

/home/kosaki/anaconda3/envs/Uni-Sign/bin/python -B \
  research/sign/scripts/score_pro_comparison.py \
  --benchmark research/sign/outputs/20260912-pro-comparison-r1/benchmark.json \
  --output research/sign/outputs/20260912-pro-comparison-r1/comparison.json
```

- [共通比較JSON：全文・原稿・指標・時間・メモリ](../outputs/20260912-pro-comparison-r1/comparison.json)
- [外部計測manifest：各コマンド・保存先・GPU集計](../outputs/20260912-pro-comparison-r1/benchmark.json)。同階層の各モデル/動画フォルダに`console.log`、`gpu_samples.jsonl`、`measurement.json`。
- [SpaMo現環境のPython・全依存一覧](../outputs/20260912-pro-comparison-r1/spamo-environment.txt)。Uni-Sign/SSVPの環境一覧は各実行保存先を参照。
- [直列実行・GPU計測補助](../scripts/benchmark_pro_videos.py)、[統一採点・整合性確認補助](../scripts/score_pro_comparison.py)
- [Uni-Sign今回07](../uni-sign/Uni-Sign/outputs/20260912-pro-comparison-r1/07_whats_your_name_pro/results.json)、[今回08](../uni-sign/Uni-Sign/outputs/20260912-pro-comparison-r1/08_greetings_pro/results.json)
- [SpaMo個別報告](../SpaMo/reports/2026-09-12-pro-07-08-comparison.md)、[SSVP個別報告](../ssvp_slt/reports/2026-09-12-pro-07-08-comparison.md)

全6件の正常終了、同じGPU・原動画hash、Uni-Sign実行時と現在の原稿hash、保存英文、独立した測定JSONと集計manifestの一致をCPU採点時に検証した。GPU計測値は生の標本ログから別担当が検算した。

サブエージェント3名がSpaMo手順・評価、SSVP手順・評価、共通指標と計測の独立検算を分担。主担当がGPU処理を直列に実行し、全体比較をまとめた。追加したのはローカル計測・採点補助と報告で、学習・共通推論API・サービス化は行っていない。動画・特徴・pose・重み・生の参照原稿はGit対象外領域に保持する。

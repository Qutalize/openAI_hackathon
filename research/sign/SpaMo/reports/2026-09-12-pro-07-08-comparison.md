# 追加ASL動画07・08：SpaMo推論と3モデル比較用計測

2026-09-12。ユーザー指定の追加動画2本を、第三者提供のSpaMo-Sign-VLA How2Sign重みで英語へ翻訳した。
入力言語はASL（ユーザー確認済み）、出力言語は英語。学習・文章補正は行っていない。
他の2モデルと同じ原動画を使い、GPU実行は直列に管理した。各動画は新規プロセスで1回ずつ実行した。

## 推論結果

2本とも終了コード0、全871項目のstrictロードに成功し、英文を生成した。
07は名前を尋ねる原稿に対して数字を列挙し、原稿の意味を再現できなかった。
08は自己紹介に近い表現を生成したが、名前を誤認し、原稿にない挨拶・視聴への謝辞を付加した。
今回の入力でも正確な翻訳は未達。意味の評価は原稿と生成文の比較であり、ASL専門家による映像の再注釈ではない。
信頼度はモデルから提供されず、`null` として記録した。

| 入力 | 未補正の出力英文 | 原稿との相違 |
|---|---|---|
| 07_whats_your_name_pro | `one, two, three, four.` | 名前を尋ねる質問と無関係な数字列 |
| 08_greetings_pro | `hi, i'm robert todd and thank you for watching.` | 自己紹介の形式は部分的に近いが、名前が違い、原稿にない内容を追加 |

全文・正解原稿・共通指標は3モデルの[共通採点JSON](../../outputs/20260912-pro-comparison-r1/comparison.json)を参照。
旧SpaMo採点のstemmed ROUGEとUni-SignのROUGEは設定が異なるため、今回のモデル間比較には共通採点のみを使用する。

| 対象 | BLEU-4 ↑ | ROUGE-L F × 100 ↑ | WER ↓ | 単語編集数／原稿語数 | 完全一致 |
|---|---:|---:|---:|---:|---:|
| 07 | 2.76 | 0.00 | 133.33% | 4／3 | 0／1 |
| 08 | 3.75 | 0.00 | 225.00% | 9／4 | 0／1 |
| 2本全体 | 2.23 | 0.00 | 185.71% | 13／7 | 0／2 |

採点はUni-Signの既存関数に統一。BLEUはmixed case・13a tokenization・exp smoothingのcorpus値で、
2本全体は文別値の平均ではない。ROUGEは上流`rouge` packageのROUGE-L F値の文平均×100。
WERは小文字化・句読点除去・語中apostrophe保持後の単語編集距離を原稿語数で割った値。
挿入があるため100%を超え得る。完全一致は大小文字・句読点も区別する。
これらは文字列一致の指標で、意味の正答率ではない。短文では句読点の一致やBLEUの平滑化による非ゼロ値も生じる。

## 処理時間とGPU使用量

| 入力 | 外部CLI全体（秒） | device peak（GiB） | process-tree peak（GiB） | 平均GPU稼働率（%） |
|---|---:|---:|---:|---:|
| 07 | 46.25 | 6.435 | 6.408 | 11.12 |
| 08 | 38.22 | 6.577 | 6.551 | 27.24 |

2本の外部CLI平均は42.23秒、合計84.47秒。2本を通じたdevice peak最大値は6.577 GiB、
process-tree peak最大値は6.551 GiB、CLI時間で重み付けした平均GPU稼働率は18.41%。

外部CLI時間はプロセス開始から終了検出まで。import、モデル読込、動画前処理、英文生成、
ハッシュ計算と出力保存を含み、終了検出には約0.2秒のポーリング分解能がある。
OSやディスクキャッシュは消去していないため、厳密なcold cache性能や常駐モデルのwarm latencyではない。

GPUはNVIDIA RTX A6000。nvidia-smiを目標0.2秒間隔で標本化し、07は231標本、08は191標本を得た。
最大観測間隔はそれぞれ0.284秒、0.234秒。両実行の開始時device使用量は21 MiB、既存compute processなし、
計測エラーと無関係なcompute processの検出はなかった。
device peakはGPU全体、process-tree peakは実行プロセスと観測した子プロセスのcompute使用量の合計。
GiBへの換算はMiB÷1024。標本間の瞬間ピークを保証する値ではない。
平均GPU稼働率はCPU処理・モデル読込・記録時間を含むCLI全体の時間加重平均であり、推論中だけの稼働率ではない。

以下はSpaMo内部の補助計測で、上表と測定範囲が違う。

| 入力 | 特徴抽出（秒） | 翻訳モデル読込（秒） | 英文生成（秒） | 内部全体（秒） | PyTorch allocated peak（GiB） |
|---|---:|---:|---:|---:|---:|
| 07 | 23.47 | 8.12 | 0.268 | 37.80 | 5.487 |
| 08 | 23.48 | 6.51 | 0.610 | 35.95 | 5.559 |

特徴抽出にはCLIP・VideoMAEの読込を含む。内部全体はimportと初期CUDA準備を除き、重みハッシュ計算を含む。
PyTorch allocated peakはアロケータが把握するテンソル用メモリで、nvidia-smiのdevice/process使用量と同一ではない。
他モデルの生成だけの時間と外部CLI時間を混ぜて速度順位を付けない。

## 再現条件

- 追加学習・ICLなし。音声ストリームと`script.txt`をモデルへ渡さない。
- SpaMo派生コードrevision：`d34bc0b62927a5b1b1b3f4fefcc0828c3f0b9983`。
- 特徴抽出コードrevision：`aee7f8b6ea8201b710690adcce6f46260dd11bba`。
- checkpoint SHA256：`140d412d232407cfc3409ba5faf8bb96ede276aadf0223b156c7e3bd6ec37ee3`。
- 専用環境：`.venv`、PyTorch `2.0.1+cu117`、CUDA runtime `11.7`。依存固定は[lockfile](../requirements-inference.lock.txt)。
- 前処理：元FPS（29.970）、RGBのみ。中央を210:260へcropしOpenCVで210×260へresize。
- 空間特徴：CLIP S²のscale=1,2、2048次元。動き特徴：VideoMAEの16フレーム窓、stride=8、末尾の不完全窓は除外。
- 07は90フレーム・動き10窓、08は119フレーム・動き13窓。空間8トークンと動き1トークンを交互に結合。
- 生成：beam=5、samplingなし、length_penalty=1.0、max_length=64、seed=0。
- 原著者の公式How2Sign checkpointであることや、学習時と現行配布コードの完全な一致は未確認。[重み調査記録](2026-09-12-how2sign-weight-search.md)を参照。

プロジェクトルートで実行した共通計測コマンド：

```bash
python3 -B research/sign/scripts/benchmark_pro_videos.py \
  --run-name 20260912-pro-comparison-r1
```

補助が起動した各モデルの正確なコマンドは共通出力内の`command.txt`に保存した。
再実行時は未使用の`--run-name`を指定する。

## 保存先

- [07のモデル出力](../outputs/20260912-pro-comparison-r1/07_whats_your_name_pro/result.json)
- [08のモデル出力](../outputs/20260912-pro-comparison-r1/08_greetings_pro/result.json)
- [共通計測結果](../../outputs/20260912-pro-comparison-r1/benchmark.json)
- [07の外部計測](../../outputs/20260912-pro-comparison-r1/SpaMo-07_whats_your_name_pro/measurement.json)
- [08の外部計測](../../outputs/20260912-pro-comparison-r1/SpaMo-08_greetings_pro/measurement.json)

入力SHA256と前処理特徴は各モデル出力、nvidia-smi標本列とconsoleログは共通計測ディレクトリに保存。
生データ・特徴・生ログはGit対象外。2本・各1回の実測であり、一般的な翻訳精度や速度分布の推定ではない。

# SSVP-SLT / SONAR：ASL動画07・08の精度・速度・GPU計測

実施日：2026-09-12。入力言語はASL（ユーザー確認）、出力言語は英語。
2本とも推論は成功したが、未補正の英文は原稿の意味と一致しなかった。
CLI全体は148.29秒・181.08秒、GPU全体の観測ピークは8.048GiB・8.065GiBだった。
主な待ち時間はCPUで動くdlib顔検出だった。

## 入力と未補正の英文

3モデル共通の原動画を使用し、音声・正解原稿・追加の文脈はモデルへ渡していない。
原稿は推論後の評価だけに使用した。原動画は変更していない。

| 入力ID | 原稿 | 未補正のモデル出力 | 意味の評価 |
|---|---|---|---|
| 07_whats_your_name_pro | What's your name? | Yes. Very. | 名前を尋ねる質問が肯定的な短い応答になり、意味不一致。 |
| 08_greetings_pro | I am named <参照名>. | We are 6.6. | 自己紹介・参照名を保持せず、複数主語と数値を生成。意味不一致。 |

参照名は管理対象の要約では伏せ、原稿全文はローカルの共通採点JSONに保持した。

両方1280×720、29.97002997fps。OpenCVメタデータでは07は90フレーム・3.003秒、08は119フレーム・3.970633秒。
入力SHA256は07が`4cd02d416f69bcb57e5f8ad9a69ff828da7c21fc79203638eeda4037df409723`、
08が`3e6af7e9c497f6e7352e66d7b4df5d52d420fb81a858962e70558bac54831650`。

## 原稿との一致度

3モデル共通の既存Uni-Sign採点関数を、保存済みの未補正英文に適用した。
集計元は[comparison.json](../../outputs/20260912-pro-comparison-r1/comparison.json)。

| 入力 | BLEU-4 ↑ | ROUGE-L F値 ↑ | WER ↓ | 文字列完全一致 |
|---|---:|---:|---:|---:|
| 07 | 7.99 | 0.00 | 100.00% | 0/1 |
| 08 | 12.44 | 0.00 | 100.00% | 0/1 |
| 2本全体 | 7.05 | 0.00 | 100.00% | 0/2 |

BLEUはmixed case・13a tokenization・exp smoothingを使用し、全体値はcorpus BLEUで文別平均ではない。
ROUGE-Lは既存rouge packageの文別F値平均×100。
WERは小文字化・句読点除去（語中apostrophe保持）後、全編集数7/全原稿語数7。
完全一致は大小文字・空白・句読点を区別する。
BLEU・ROUGEは正答率ではなく、BLEUは平滑化や句読点の一致で意味不一致でも非ゼロになる。
この2本では意味の評価でも両方不一致だった。

## 速度とGPU使用量

同じNVIDIA RTX A6000で、各動画を新規CLIプロセスとして1回ずつ直列実行した。
外部の共通計測器はCLI起動から終了検出までを計測し、モデルロード・前処理・推論・入力/重みハッシュ・結果保存を含めた。
OSファイルキャッシュは消去しておらず、モデル常駐時の定常推論速度は測定していない。

| 入力 | CLI全体 | GPU全体ピーク | 対象プロセス群ピーク | GPU平均使用率 | GPU最大使用率 |
|---|---:|---:|---:|---:|---:|
| 07 | 148.29秒 | 8.048GiB | 8.021GiB | 0.56% | 50% |
| 08 | 181.08秒 | 8.065GiB | 8.039GiB | 0.37% | 66% |
| 2本集計 | 平均164.68秒 | 最大8.065GiB | 最大8.039GiB | 時間加重平均0.45% | 最大66% |

VRAMは`nvidia-smi`を要求間隔0.2秒で監視した観測ピークで、MiBを1024で割ってGiB表示した。
GPU全体には実行直前の21MiBを含む。baseline差は07が8.027GiB、08が8.045GiB。
対象プロセス群はwrapperとその子プロセスのGPUメモリ合算で、GPU全体値やPyTorch allocated値とは範囲が異なる。
741回・905回採取し、最大採取間隔は0.238秒・0.233秒。監視エラー・無関係な計算プロセスは観測されなかった。
短時間のピークは取りこぼし得るため、厳密な最小必要VRAMとは扱わない。
GPU平均使用率はCPU処理・モデルロード・記録中も含むCLI全体でのdevice使用率である。

SSVP内部の時間内訳は次のとおり。上流の`time.time()`によるCUDA同期を追加しない参考値で、他モデルの内部タイマーとは境界が異なる。

| 入力 | モデルロード | 前処理全体 | うちCPU顔検出 | 特徴抽出 | 翻訳 | 上流子プロセス全体 |
|---|---:|---:|---:|---:|---:|---:|
| 07 | 20.842秒 | 109.298秒 | 109.049秒 | 0.492秒 | 0.141秒 | 139.959秒 |
| 08 | 18.702秒 | 146.622秒 | 146.066秒 | 0.486秒 | 0.175秒 | 174.955秒 |

顔検出は前処理全体の内数。GPU平均使用率が低いことは、処理時間の大半をCPU顔検出が占める結果と整合する。
現在の設定では約3〜4秒の動画に約148〜181秒かかり、リアルタイムで英文を返せる速度ではない。
顔検出の縮小入力やCUDA版dlibを使った場合の速度・出力変化は今回未検証。

## 環境・前処理・再現

上流revisionは`7ed332b0db35884a36b73019ca29bf0755537def`。
Python 3.10.21、PyTorch 2.2.2+cu121、CUDA 12.1、dlib 19.24.6（`DLIB_USE_CUDA=False`）。
環境は既存の専用`.venv/`で、学習・重み変更・外部LLMによる文章補正は実施していない。
SONAR 0.2.1互換patchを適用した既存推論経路を使用した。2本ともSignHieraとASL encoderの重みロードは`All keys matched successfully`を確認した。

前処理はdlib CNN顔検出を16フレームごとに実行し、顔枠を拡張して正方形crop→224×224。
`detection_downsample=false`、target FPS 25、sampling rate 2、128フレーム窓、stride 64、短動画の末尾paddingを維持した。
SignHieraはCUDA autocast fp16、SONAR ASL encoder・decoderはfp16、英語指定`eng_Latn`、既存beam search設定を使用。
SignHiera重みSHA256は`df84d487cafa3fc0390eb5c96d9cef2586467ea07f76d2e9e681aefb82317c4b`、
ASL encoderは`c042363959593265644d929876c1f46afef8a6c73dea3e89410f61171bd2f005`。
decoder・tokenizerを含む一覧は[artifacts.sha256](../artifacts.sha256)、依存版は[lockfile](../requirements-inference.lock.txt)を参照。

プロジェクトルートからの推論コマンド。保存先が既にある場合は新しい名前を指定する。

```bash
research/sign/ssvp_slt/.venv/bin/python -B -u research/sign/ssvp_slt/scripts/run_video.py \
  data/sign/07_whats_your_name_pro/whatisyourname.mp4 \
  --output research/sign/ssvp_slt/outputs/20260912-pro-comparison-r1/07_whats_your_name_pro
research/sign/ssvp_slt/.venv/bin/python -B -u research/sign/ssvp_slt/scripts/run_video.py \
  'data/sign/08_greetings_pro/mynameis (2).mp4' \
  --output research/sign/ssvp_slt/outputs/20260912-pro-comparison-r1/08_greetings_pro
```

モデル出力は[07のresult.json](../outputs/20260912-pro-comparison-r1/07_whats_your_name_pro/result.json)、
[08のresult.json](../outputs/20260912-pro-comparison-r1/08_greetings_pro/result.json)。
同じディレクトリに`prediction.txt`、`inference.log`、`environment.txt`、`command.txt`、Hydra設定を保存した。
外部計測は[benchmark.json](../../outputs/20260912-pro-comparison-r1/benchmark.json)と、その隣の`ssvp_slt-<入力ID>/`配下に保存した。
共通計測器は[benchmark_pro_videos.py](../../scripts/benchmark_pro_videos.py)。

今回の2本ではUni-Signが意味の一致・原稿との一致度・CLI全体時間でSSVP-SLTより良好だった。
SSVP-SLTのGPUメモリはUni-Signより少なく、SpaMoのSign-VLA経路より多かった。
この比較は指定された短文2本・各1回・現在の環境と前処理に限る。
原稿はASL話者による独立した再アノテーションではなく、モデル一般の精度順位や失敗原因の特定には使えない。
信頼度は上流が返さないため`null`であり、推論成功と翻訳の正しさを区別して記録した。

Codexの主担当が全モデルのGPU推論・共通計測・採点を実行し、SSVP担当サブエージェントが既存経路の確認と本報告を作成した。

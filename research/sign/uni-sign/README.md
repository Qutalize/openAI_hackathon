# Uni-Sign：自前動画の単体推論

2026-09-12 Git管理更新：既存の上流コード・設定・文書をルートのGitへ集約しました。
この作業ツリーでは上流コードは配置済みで、以下の過去の準備例にある上流への `git clone`・`git checkout`・パッチの再適用は不要です。
動画・重み・生出力は引き続きローカル管理です。上流ディレクトリ全体をGit対象外とする従来の記述は、この方針で置き換えます。
取得元revision、除外資材の準備、復元方法は [Git管理の集約](../../../docs/07-git-consolidation.md) を参照してください。

動画07/08をSpaMo・SSVP-SLTと同じ外部計測方法で再実行し、前回と同じ英文を得た。
Uni-SignのCLI時間は平均15.21秒/本、GPUメモリ観測ピークは13.17 GiB。
[3モデルの精度・速度・GPU比較](../reports/2026-09-12-pro-three-model-comparison.md)に計測範囲と全結果を記録した。

追加ASL動画07/08も評価した。出力は`What's your name like?`と`My name is Sedrick.`。
名前の質問・自己紹介という内容に近づいたが、07は余分な語、08は名前の誤認が残る。
2本のBLEU-4は22.59、ROUGE-Lは28.57、参考WERは71.43%。
[原稿との比較・全出力・再現手順](reports/2026-09-12-self-07-08-pro-evaluation.md)を参照。

2026-09-12：How2Sign pose-onlyの学習済み重みを用いて、自前動画2本から英文生成まで実行した。
学習・ファインチューニング・文章補正は行っていない。両動画の生成英文は正解ラベルと不一致。
同日の追加調査中、ユーザーが入力をASL、各`script.txt`を正解ラベルと確認した。
正しい翻訳の再現成功とは扱わない。数値・姿勢への感度は実測したが、根本原因は未確定。
詳細は[翻訳不一致の調査記録](reports/2026-09-12-how2sign-mismatch-investigation.md)を参照。

同日の追加検証で、How2Sign testから固定した12組を取得して評価した。
配布poseでBLEU-4 14.96、同じ動画からの再抽出で12.83。両経路12/12件が実行成功し、
主旨が合う例もあるが誤訳が多い。自前動画だけを失敗原因にはできず、モデル性能の限界も残る。
少数診断であり全test再現ではない。[評価データ12組の比較・再現手順](reports/2026-09-12-how2sign-test-subset.md)を参照。
自前2本も同じ方法で採点し、BLEU-4 2.35、ROUGE-L 5.56だった。
[指標の説明・GT/予測例・自前との比較](reports/2026-09-12-score-examples-comparison.md)に参考WERと入力条件の違いも記録した。

さらに自前動画へ固定crop・縮小・下余白追加を行い、原動画/画素同一の再保存対照を含む5条件×2本を再評価した。
人物の配置はHow2Sign参照に近づいたが、正しい質問・挨拶は得られず、翻訳改善は確認できなかった。
今回の原動画再実行はBLEU-4 2.01、crop＋縮小は2.65。ただし画素同一の対照でも出力が変わり、数値差だけでは改善と扱えない。
[前処理仕様・全予測・再現手順](reports/2026-09-12-self-preprocessing-evaluation.md)を参照。
同じ10条件の保存poseを映像へ重ね、左右の手の拡大比較付き動画も作成した。
[pose重ね合わせ動画一覧・凡例・再現手順](reports/2026-09-12-pose-overlay-videos.md)から参照できる。poseの再推定は行っていない。

追加の03〜06（石けん・水の要求文、横/縦）も原動画で評価した。4/4件生成成功、BLEU-4 1.12、ROUGE-L 0、参考WER391.67%で、要求の意味は不一致。
縦動画も実ファイルは1280×720の黒帯付きだったため、黒帯だけを除去した420×720入力も比較したが正訳にはならなかった。
今回は全8推論条件で使用pose点の低信頼mask率0%。座標精度の正しさは未確認。
[追加4本の全結果・黒帯比較・pose動画](reports/2026-09-12-self-03-06-evaluation.md)に記録した。

03〜06にはさらに人物crop・縮小・参照縦横比への左右余白を適用し、対照込み5条件×4本を評価した。
余白＋縮小はBLEU-4 2.14 / ROUGE-L 16.03だったが、石けん・水の要求として正訳は得られなかった。
[全20予測・前処理動画・元画角の骨格動画](reports/2026-09-12-self-03-06-preprocessing-comparison.md)を参照。

06の`crop_pad_resize`について保存poseから誤訳をtoken IDまで再現し、実生成beamのcross-attention、
GTのteacher forcing、部位別中間特徴、時間窓・手形・生成設定への介入を実行した。
両手区間は`heavy`、口元区間は`thirsty`の確率を支えたが、GTとの語義対応や根本原因は未確定。
[時間軸の図・実測値・再実行手順](reports/2026-09-12-water-temporal-attention.md)に観測と限界を分けて記録した。

- モデルの対象：ASL（米国手話）→英文。日本手話・BSL対応ではない。
- 上流：[ZechengLi19/Uni-Sign](https://github.com/ZechengLi19/Uni-Sign)
- 上流revision：`eed438bcb49e30405cd6ccdfcccca330c134e830`
- 実験記録：[2026-09-12-how2sign-self-videos.md](reports/2026-09-12-how2sign-self-videos.md)

## 配置

ユーザー指定に従い、既存checkoutの名前を維持し、その内部に重みと実行出力を置く。

```text
research/sign/uni-sign/
  README.md
  scripts/run_online.py        # 上流推論を呼び出す保存・記録用の補助
  patches/                    # 上流への小さな修正の再現用
  reports/                    # 日本語の検証記録
  Uni-Sign/                   # 既存の上流checkout、Git管理対象外
    config.py
    weights/
      how2sign_pose_only_slt.pth
      mt5-base/
      torch-cache/hub/checkpoints/  # 人物・全身姿勢検出のONNX
    outputs/                  # 生出力・ログ・依存一覧、Git管理対象外
```

## 再実行

作業ディレクトリはプロジェクトルート。`Uni-Sign` conda環境のPythonを使用する。

```bash
conda run --no-capture-output -n Uni-Sign python -B \
  research/sign/uni-sign/scripts/run_online.py \
  data/sign/01_whats_your_name/original.mp4

conda run --no-capture-output -n Uni-Sign python -B \
  research/sign/uni-sign/scripts/run_online.py \
  data/sign/02_greetings/original.mp4
```

別の動画は最後の入力パスを変更する。デフォルトでは毎回一意のディレクトリを作り、保存先を画面へ表示する。
`--output-dir <新しいディレクトリ>` を追加して保存先を指定できる。既存の保存先は上書きせずエラーになる。

| 保存ファイル | 内容 |
|---|---|
| `prediction.txt` | 成功時のみ作成。未補正の生成英文1行 |
| `inference.log` | 上流の標準出力・標準エラー。失敗時も保存 |
| `result.json` | 実行状態、英文、経過時間、入力・重みSHA256、revision、依存バージョン、前処理、実際のONNX provider |
| `command.txt` | 実際に呼び出した上流Pythonコマンド。環境変数と作業ディレクトリは`result.json`を参照 |
| `environment.txt` | 実行環境の`pip freeze`。追加修正を含む同梱RTMLibの復元は下記も必要 |

上流は `python -m demo.online_inference` として呼び出す。How2Sign、SLT、pose-only、最大256フレーム、seed 42、BF16、beam 4を使用する。
`--finetune`はこの推論経路では重み読み込み用の引数であり、学習はしない。
正解原稿は読み込まない。音声は使わず、動画は外部へ送信しない。
姿勢座標はメモリ上で処理し、骨格ファイル・字幕動画・SRTを生成しない。
翻訳の信頼度は上流から提供されないため`null`で記録する。

## 初回準備の再現

この作業環境では準備済み。以下は別環境で再現する場合の追加手順であり、先に上流requirementsに合う専用環境を用意する。
確認環境はPython 3.9.25、PyTorch 2.1.1+cu121、NumPy 1.22.4、Transformers 4.40.0。
以下の作業ディレクトリは `research/sign/uni-sign/Uni-Sign`。

```bash
conda activate Uni-Sign

hf download google/mt5-base \
  config.json generation_config.json pytorch_model.bin \
  special_tokens_map.json spiece.model tokenizer_config.json \
  --revision 2eb15465c5dd7f72a8f7984306ad05ebc3dd1e1f \
  --local-dir ./weights/mt5-base

python -m pip install -e ./demo/rtmlib-main \
  coloredlogs==15.0.1 humanfriendly==10.0

python -m pip install --no-deps onnxruntime-gpu==1.18.0 \
  --index-url https://aiinfra.pkgs.visualstudio.com/PublicPackages/_packaging/onnxruntime-cuda-12/pypi/simple/

python -m pip install \
  nvidia-curand-cu12==10.3.2.106 \
  nvidia-cufft-cu12==11.0.2.54 \
  nvidia-cuda-runtime-cu12==12.1.105
```

不足するONNX Runtime依存は既存のflatbuffers、NumPy、packaging、protobuf、sympyで満たされていることをdry-runで確認した。
`--no-deps`はこの確認を前提とし、別環境では不足依存を先に確認する。
CUDA 12・cuDNN 8版のONNX Runtime 1.18.0を選ぶ根拠は[公式互換表](https://onnxruntime.ai/docs/execution-providers/CUDA-ExecutionProvider.html#requirements)。
同版のPyPI配布はCUDA 11.8版なので、上記の公式CUDA 12 feedを使用する。

上流checkoutが未修正の場合のみ、パッチを適用する。今回のcheckoutには適用済み。

```bash
git apply --check ../patches/mt5-path.patch ../patches/inference-only.patch ../patches/ort-cuda-provider.patch
git apply ../patches/mt5-path.patch ../patches/inference-only.patch ../patches/ort-cuda-provider.patch
```

- `config.py`：mT5配置先を`./weights/mt5-base`へ変更。
- `utils.py`：`UNI_SIGN_INFERENCE_ONLY=1`の場合だけ未使用のDeepSpeed importを省く。通常実行・学習時の既定動作は維持。
- 同梱RTMLib：実際のproviderをログ表示し、CUDA初期化に失敗した場合はCPUへの無通知フォールバックを拒否。
- 保存補助：上記フラグと、PyTorchおよびNVIDIA実行時ライブラリの`LD_LIBRARY_PATH`を子プロセスへ設定する。

GPUドライバの変更、CUDAコンパイラの導入、重みの変更は行っていない。

## 制約と残課題

- `pip check`はDecord 0.6.0のwheel内部タグ`cp36-cp36m`を理由に非ゼロ終了する。既存の配布メタデータの問題は未解消。
  Python 3.9でDecord importと1本目の`VideoReader`による121フレーム・先頭画像の読み込みは確認した。パッケージメタデータは書き換えていない。
- 両動画は256フレーム以下で間引きなし。長い動画は上流のランダムフレーム選択が入る。自動文分割・長動画翻訳は未検証。
- providerにCPUも表示されるのはCUDA providerの不在とは異なる。上流ONNXには形状計算などCPU実行に割り当てられるノードがある。
- 同じseedでもCPU/GPUの姿勢推定結果から異なる英文が出た。追加診断では固定pose・固定精度の反復は一致したが、演算精度や抽出条件で文が変わる場合があった。bit単位の一般的な再現性は保証しない。
- 自前動画はユーザーがASLと確認済み。個々の表現・区間境界の独立確認と撮影条件の適合性は残課題。モデル出力だけから入力手話の意味を断定しない。

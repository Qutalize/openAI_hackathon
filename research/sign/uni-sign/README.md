# Uni-Sign：環境構築・重みの準備・動画1本の推論

このディレクトリでは、**How2Signで学習済みのpose-onlyモデルを使い、ASL（米国手話）の動画から英文を生成**します。日本手話・BSL用の手順ではありません。追加学習、glossの出力、LLMによる文章補正は行いません。

現在の共有環境では、専用conda環境・重み・必要なコード修正が準備済みです。初めて使う人は「[既存環境で動かす](#既存環境で動かす)」、別マシンで準備する人は「[環境を新規構築する](#環境を新規構築する)」から進めてください。

2026-09-13改稿。2026-09-12のローカルCodexチャット、condaの履歴、実行ログ、環境一覧、現行コードを照合して整理しました。**既存環境での推論成功と、新しい環境へのインストール手順の再実行は区別しています。** 今回は既存環境のimportとCLI起動を確認し、環境の作り直し・重みの再取得・GPU推論は実施していません。

- [既存環境で動かす](#既存環境で動かす)
- [ディレクトリ構成](#ディレクトリ構成)
- [環境を新規構築する](#環境を新規構築する)
- [重みを準備する](#重みを準備する)
- [推論の処理内容と結果の読み方](#推論の処理内容と結果の読み方)
- [よくある問題と対処](#よくある問題と対処)
- [追加検証用スクリプトと過去の結果](#追加検証用スクリプトと過去の結果)
- [再現情報と参照先](#再現情報と参照先)

## 既存環境で動かす

以下は**プロジェクトルート**で実行します。別の場所へcloneした場合、最初の `cd` だけ自分の配置へ変更してください。

```bash
cd /mnt/kiso-qnap5/activities/260915_codex_hackathon

conda run --no-capture-output -n Uni-Sign python -B \
  research/sign/uni-sign/scripts/run_online.py \
  data/sign/01_whats_your_name/original.mp4
```

最後の引数を自分の動画ファイルへ変更すれば、別の動画も実行できます。空白を含むパスは引用符で囲みます。動画はGit管理外なので、新しくcloneした環境では別途用意してください。`script.txt` や正解文、事前抽出したposeは、この単体推論には不要です。

デフォルトの保存先は `research/sign/uni-sign/Uni-Sign/outputs/how2sign-<日時>-<一意な文字列>/` です。画面に表示された保存先の `prediction.txt` で英文を確認できます。

保存先を指定する例：

```bash
conda run --no-capture-output -n Uni-Sign python -B \
  research/sign/uni-sign/scripts/run_online.py \
  data/sign/02_greetings/original.mp4 \
  --output-dir research/sign/uni-sign/Uni-Sign/outputs/my-first-run
```

`--output-dir` は**存在しないディレクトリ**を指定します。同じ名前で再実行すると上書きを拒否するため、省略するか新しい名前にしてください。

`conda activate Uni-Sign` 済みなら、上記の `conda run --no-capture-output -n Uni-Sign python` を `python` に置き換えられます。この共有マシンの環境実体は `/home/kosaki/anaconda3/envs/Uni-Sign/` です。別マシンではこの絶対パスを流用しません。

## ディレクトリ構成

大文字の `Uni-Sign/` が上流コード、小文字の `uni-sign/` がこのプロジェクトの検証単位です。重みと主な実行出力は、既存配置を維持して**内側の `Uni-Sign/` に置きます**。

```text
research/sign/uni-sign/
├── README.md                         # この手順書
├── scripts/                          # 自作の実行・評価・可視化補助
│   ├── run_online.py                 # 最初に使う：動画1本 → 英文と実行記録
│   └── ...                           # 詳細は末尾のスクリプト一覧
├── patches/                          # 過去に適用した3つの修正の記録
├── reports/                          # 日本語の検証結果・再実行手順
├── outputs/                          # 初期の撮影確認画像など（主な推論保存先とは別）
└── Uni-Sign/                         # 修正済みの上流コード。ルートのGitで管理
    ├── README.md                     # 上流の説明
    ├── requirements.txt              # 上流の依存定義
    ├── config.py                     # mT5のローカル配置、データセットのパス
    ├── models.py                     # Uni-Sign本体とmT5
    ├── datasets.py                   # poseの整形・部位別正規化など
    ├── utils.py                      # 推論専用時のDeepSpeed import回避を含む
    ├── demo/
    │   ├── online_inference.py       # 動画読込 → 姿勢抽出 → 英文生成
    │   ├── pose_extraction.py        # 姿勢抽出用の上流CLI
    │   └── rtmlib-main/              # 修正済みRTMLib。ここをeditable installする
    ├── stgcn_layers/                 # 骨格系列の処理
    ├── external_metrics/            # BLEU/ROUGE等の評価コード
    ├── fine_tuning.py, script/       # 上流の学習・データセット評価用
    ├── docs/, download_scripts/     # 上流資料・データ取得補助
    ├── data/                        # 上流のラベル類。実データはGit管理外
    ├── out/                         # 上流同梱の出力例。今回の結果保存先ではない
    ├── weights/                     # 以下は全てGit管理外
    │   ├── how2sign_pose_only_slt.pth
    │   ├── mt5-base/                # mT5の重み・設定・tokenizer
    │   ├── torch-cache/hub/checkpoints/
    │   │   ├── yolox_tiny_8xb8-300e_humanart-6f3252f9.onnx
    │   │   └── rtmw-dw-l-m_simcc-cocktail14_270e-256x192_20231122.onnx
    │   └── hf-cache/                # Hugging Face関連キャッシュ
    └── outputs/                     # 主な推論・評価結果。Git管理外
        ├── setup-20260912/          # 構築前後のpip freeze、pip check
        ├── how2sign-.../            # run_online.pyの自動保存先
        └── 20260912-.../            # 過去の実験・失敗ログ・pose・可視化
```

共通入力はプロジェクトルートの `data/sign/<入力ID>/` にあります。conda環境はこのツリーの外です。

上流コードはこのプロジェクトに取り込み済みです。**この手順では `Uni-Sign/` への再clone、入れ子の `.git` 作成、パッチ再適用は不要です。** 重み・動画・pose・生ログはGitへ追加しません。ルートリポジトリだけをcloneしても重みや入力動画は付属しません。管理方針は[Git管理の集約](../../../docs/07-git-consolidation.md)を参照してください。

## 環境を新規構築する

### 動作を確認した構成

以下は2026-09-12のGPU推論記録と、2026-09-13の既存環境確認に基づきます。最低動作要件の測定値ではありません。

| 項目 | 確認した構成 |
|---|---|
| OS / GPU | Ubuntu 24.04.3 LTS / NVIDIA RTX A6000（49,140 MiB） |
| ドライバ | 590.48.01 |
| conda環境 / Python | `Uni-Sign` / 3.9.25 |
| PyTorch / torchvision / torchaudio | 2.1.1+cu121 / 0.16.1+cu121 / 2.1.1+cu121 |
| PyTorchのCUDA runtime / cuDNN | 12.1 / 8.9.2（表示値8902） |
| Transformers / tokenizers / sentencepiece | 4.40.0 / 0.19.1 / 0.1.97 |
| NumPy / OpenCV / Decord | 1.22.4 / 4.6.0.66 / 0.6.0 |
| ONNX Runtime | `onnxruntime-gpu==1.18.0`、公式CUDA 12 feed版 |
| RTMLib | 0.0.13、同梱コードのeditable install |
| Hugging Face CLI用パッケージ | `huggingface-hub==0.36.2` |
| pip / setuptools / wheel | 26.0.1 / 80.9.0 / 0.45.1 |

この推論経路はCUDAとBF16を使います。CPUのみ、Windows、macOS、別GPUでの動作はこの手順では検証していません。短動画2本の別途比較ではGPUメモリの観測ピークが13.17 GiBでしたが、必要VRAMの厳密な下限ではありません。[計測条件](../reports/2026-09-12-pro-three-model-comparison.md)を参照してください。

### 1. 専用環境を作り、PyTorchを先に入れる

condaとNVIDIAドライバが使えるLinux環境を前提とします。以下の作業ディレクトリは**内側の `Uni-Sign/`**です。

```bash
cd /mnt/kiso-qnap5/activities/260915_codex_hackathon/research/sign/uni-sign/Uni-Sign

conda create --name Uni-Sign python=3.9.25
conda activate Uni-Sign

python -m pip install \
  torch==2.1.1+cu121 torchvision==0.16.1+cu121 torchaudio==2.1.1+cu121 \
  --index-url https://download.pytorch.org/whl/cu121

python -m pip install -r requirements.txt
```

**このインストール順序が、初回のチャットで案内された重要な対処です。** 上流READMEの `pip install -r requirements.txt` だけでは、通常のPyPIから `torch==2.1.1+cu121` が見つからず失敗しました。CUDA 12.1版のtorch一式を公式配布先から先に入れ、残りを上流requirementsから入れます。

当時の環境作成指定は `python=3.9`、実際に入ったバージョンは3.9.25でした。上の例では実測値を明示しています。ここからの新規構築手順は履歴から整理したもので、空の環境で全工程を今回再実行したものではありません。上流requirementsにも推移的依存の完全なlockはありません。

`requirements.txt` にはDeepSpeed・TensorFlowなども含まれます。このREADMEでは既存の動作環境に沿って導入しますが、学習を実行する手順ではありません。BLEURT本体・BLEURT-20重みは今回の英文生成やBLEU/ROUGE評価には不要です。

### 2. 同梱RTMLibとONNX Runtimeを入れる

同じ `Uni-Sign/`、同じconda環境で続けます。

```bash
python -m pip install -e ./demo/rtmlib-main \
  coloredlogs==15.0.1 humanfriendly==10.0

python -m pip install --no-deps onnxruntime-gpu==1.18.0 \
  --index-url https://aiinfra.pkgs.visualstudio.com/PublicPackages/_packaging/onnxruntime-cuda-12/pypi/simple/

python -m pip install \
  nvidia-curand-cu12==10.3.2.106 \
  nvidia-cufft-cu12==11.0.2.54 \
  nvidia-cuda-runtime-cu12==12.1.105

python -m pip install huggingface-hub==0.36.2
```

上流demo READMEの無指定の `pip install onnxruntime-gpu cuda-toolkit` をそのまま使った構成ではありません。今回のPyTorchはCUDA 12.1・cuDNN 8なので、**ORT 1.18.0のCUDA 12・cuDNN 8版**を選びました。同じORT 1.18系でもPyPI版はCUDA 11.8系、CUDA 12版の1.18.1はcuDNN 9を要求します。[公式互換表](https://onnxruntime.ai/docs/execution-providers/CUDA-ExecutionProvider.html#requirements)、[公式インストール案内](https://onnxruntime.ai/docs/install/)が根拠です。

`--no-deps` は、既存のflatbuffers・NumPy・packaging・protobuf・sympyでORT依存を満たしていたため使いました。新規環境でも依存チェックを行ってください。既存のTensorFlow 2.9.1と共存していた値は `flatbuffers==1.12`、`protobuf==3.19.6` です。ORTのためにこれらを無指定で更新する手順にはしていません。

RTMLibは `pip install rtmlib` ではなく、**このツリーの `demo/rtmlib-main` をインストール**します。ここにはGPU providerを確認するローカル修正があります。

### 3. 適用済みのコード修正を理解する

このプロジェクトのコードには次の対処が既に入っています。通常は編集やパッチの再適用をしません。

| 対処 | 必要になった理由・動作 | 記録 |
|---|---|---|
| mT5パスを `./weights/mt5-base` に変更 | ローカルに取得したmT5を読み込む | [mt5-path.patch](patches/mt5-path.patch) |
| `UNI_SIGN_INFERENCE_ONLY=1` のときDeepSpeed importを省略 | 推論で使わないDeepSpeedのimport時に `CUDA_HOME` / `nvcc` を要求されて停止した | [inference-only.patch](patches/inference-only.patch) |
| ONNXセッションの実providerを表示し、CUDA不在ならエラー | 不足ライブラリにより姿勢推定だけCPUへフォールバックするケースを検出する | [ort-cuda-provider.patch](patches/ort-cuda-provider.patch) |
| 子プロセスの `LD_LIBRARY_PATH` を設定 | PyTorchと `nvidia/*/lib` のCUDA実行時ライブラリをORTから見つけられるようにする | [run_online.py](scripts/run_online.py) |

`run_online.py` が推論専用フラグ、ライブラリパス、キャッシュ先、上流の作業ディレクトリを設定します。上流の `demo/online_inference.py` を直接起動すると、この準備は自動で入りません。

既存環境の対処ではドライバ変更やCUDAコンパイラの追加は行っていません。DeepSpeedの通常import・学習経路の動作は未検証です。未修正の上流コードと比較・復元したい場合は[取り込み時の差分](../../upstream-patches/sign--uni-sign--Uni-Sign.patch)を参照してください。

### 4. 環境を確認する

conda環境をactivateした状態で実行します。

```bash
python -B - <<'PY'
import sys
import torch
import cv2
import decord
import transformers
import onnxruntime as ort
import rtmlib

print("Python:", sys.version)
print("torch:", torch.__version__)
print("CUDA runtime:", torch.version.cuda)
print("cuDNN:", torch.backends.cudnn.version())
print("CUDA available:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("GPU:", torch.cuda.get_device_name(0))
    print("BF16 supported:", torch.cuda.is_bf16_supported())
print("OpenCV:", cv2.__version__)
print("Decord:", decord.__version__)
print("Transformers:", transformers.__version__)
print("ORT:", ort.__version__, ort.get_available_providers())
print("RTMLib source:", rtmlib.__file__)
PY

python -m pip check
```

CUDAとBF16の確認値が `True`、RTMLibのパスがこのプロジェクトの `demo/rtmlib-main/rtmlib/` を指すことを確認します。`get_available_providers()` は利用候補の一覧なので、**実際にCUDAセッションが作れたかは、動画推論のログでも確認**します。

既存環境の `pip check` は `decord 0.6.0 is not supported on this platform` で非ゼロ終了しました。内部wheelタグが `cp36-cp36m` である一方、Python 3.9でimportと動画読込は成功しています。この既知の不整合は未修正です。他の依存エラーまで無視してよいという意味ではありません。

構築当時の一覧は [environment-before.txt](Uni-Sign/outputs/setup-20260912/environment-before.txt)、[environment-after.txt](Uni-Sign/outputs/setup-20260912/environment-after.txt)、[pip-check.txt](Uni-Sign/outputs/setup-20260912/pip-check.txt) にあります。これらはローカル記録なのでclone先には付属しません。また古いfreezeのRTMLib行は上流Git URLを指しており、そのまま `pip install -r` してもローカル修正は復元できません。上記のeditable installを使ってください。

## 重みを準備する

### 何をダウンロードするか

**この手順で選ぶUni-Signの重みは `how2sign_pose_only_slt.pth` です。** 学習途中の汎用checkpointや別データセットの重みに置き換えません。

| 必要な資材 | 用途 | 配置・取得方法 |
|---|---|---|
| `how2sign_pose_only_slt.pth`（約1.19 GB） | How2Sign / ASL → 英文の学習済みUni-Sign | `Uni-Sign/weights/` へ手動取得 |
| `google/mt5-base` の6ファイル（重み約2.33 GB） | モデル生成時のmT5・tokenizer読込に必要。Uni-Sign checkpointがあっても必要 | `Uni-Sign/weights/mt5-base/` へ手動取得 |
| YOLOX tiny ONNX（約20 MB） | 動画内の人物検出 | 初回推論で自動取得 |
| RTMW lightweight ONNX（約129 MB） | 全身・手・顔の133点の姿勢推定 | 初回推論で自動取得 |

容量は配置済みファイルのおおよその10進表記です。重みだけで約3.7 GBあり、別にPython環境・ダウンロード時の一時領域・動画・出力の容量が必要です。

[Uni-Sign公式配布](https://huggingface.co/ZechengLi19/Uni-Sign/tree/main)にはOpenASL用や他タスク用の重みもありますが、この保存補助はHow2Signのファイル名とSHA256に固定されています。OpenASL版・RGB-pose版との比較はこの単体推論の選択肢には実装していません。`--rgb_support` もこの手順では付けません。How2Sign全データセットや学習用ラベルのダウンロードは、動画1本の推論には不要です。

### 1. Uni-SignとmT5を取得する

conda環境 `Uni-Sign` をactivateし、**内側の `Uni-Sign/`** で実行します。

```bash
mkdir -p weights

hf download ZechengLi19/Uni-Sign how2sign_pose_only_slt.pth \
  --local-dir ./weights

hf download google/mt5-base \
  config.json generation_config.json pytorch_model.bin \
  special_tokens_map.json spiece.model tokenizer_config.json \
  --revision 2eb15465c5dd7f72a8f7984306ad05ebc3dd1e1f \
  --local-dir ./weights/mt5-base
```

mT5はrevision固定です。Uni-Sign checkpointの当初のダウンロードrevisionは未記録で、上の取得例も可変の `main` を使います。そのため**下記のSHA256で実験時と同じ内容か確認**します。`run_online.py` もHow2Sign checkpointのハッシュが違えば開始前に拒否します。

```bash
sha256sum -c <<'SHA256'
1bfd5f3312f04e4736f0a52f4ef9535916e6de9676a2a0d00c708748683fb00d  weights/how2sign_pose_only_slt.pth
180573b534144580f04af026da62bf71bc976ee1b7eb311b8945e2fefde8d614  weights/mt5-base/pytorch_model.bin
SHA256
```

配置の完成形：

```text
weights/
├── how2sign_pose_only_slt.pth
└── mt5-base/
    ├── config.json
    ├── generation_config.json
    ├── pytorch_model.bin
    ├── special_tokens_map.json
    ├── spiece.model
    └── tokenizer_config.json
```

`config.py` の `mt5_path = "./weights/mt5-base"` と対応します。tokenizerだけ、またはcheckpointだけでは動きません。

### 2. 姿勢検出用ONNXを揃える

初回の `run_online.py` 実行時、同梱RTMLibが次のOpenMMLab配布ZIPをダウンロード・展開します。

- [YOLOX tiny（人物検出）](https://download.openmmlab.com/mmpose/v1/projects/rtmposev1/onnx_sdk/yolox_tiny_8xb8-300e_humanart-6f3252f9.zip)
- [RTMW lightweight（全身姿勢）](https://download.openmmlab.com/mmpose/v1/projects/rtmw/onnx_sdk/rtmw-dw-l-m_simcc-cocktail14_270e-256x192_20231122.zip)

URLの定義は同梱の [wholebody.py](Uni-Sign/demo/rtmlib-main/rtmlib/tools/solution/wholebody.py) の `MODE["lightweight"]`、取得処理は [file.py](Uni-Sign/demo/rtmlib-main/rtmlib/tools/file.py) にあります。

保存先は `weights/torch-cache/hub/checkpoints/` です。ZIP内の `end2end.onnx` をZIPのベース名に対応する `.onnx` へ改名して保存します。2回目以降はそのキャッシュを使います。初回にはネット接続が必要ですが、入力動画を送信する処理ではありません。

ネット接続のない実行先では、準備済み環境の上記2つの `.onnx` を、ディレクトリ構成のとおり同名で配置できます。取得・配置後の照合例（引き続き `Uni-Sign/` で実行）：

```bash
sha256sum -c <<'SHA256'
ceb11c07298f95c50d7c5abeb906d03340c85f23aa79e3e66966e7fb6c307250  weights/torch-cache/hub/checkpoints/yolox_tiny_8xb8-300e_humanart-6f3252f9.onnx
68db326c5c6f3273456f803eae0faf5440478369f2c3ee67258d2f36512e8d76  weights/torch-cache/hub/checkpoints/rtmw-dw-l-m_simcc-cocktail14_270e-256x192_20231122.onnx
SHA256
```

資材が揃ったら、[冒頭のコマンド](#既存環境で動かす)へ戻り、プロジェクトルートから動画1本を実行します。

## 推論の処理内容と結果の読み方

処理は次の順です。

1. 補助スクリプトが入力・必要ファイル・checkpointのSHA256を確認し、出力ディレクトリを作る。
2. 内側の `Uni-Sign/` を作業ディレクトリとして、`python -B -u -m demo.online_inference` を起動する。
3. OpenCVで映像を読み、YOLOX / RTMWで人物と姿勢を抽出する。
4. 座標を画像幅・高さで正規化し、上流の部位別正規化を適用する。
5. Uni-SignとmT5で英文を生成し、ログと結果を保存する。

固定設定は `How2Sign / SLT / pose-only`、`max_length=256`、seed 42、BF16、beam 4、`max_new_tokens=100` です。`--finetune` はこの経路では**学習済み重みを読み込む引数名**であり、学習は走りません。

音声・正解原稿・ユーザー指定のテキストpromptは使いません。モデル内部では、翻訳先言語を示す固定prefix `Translate sign language video to English: ` を付けます。入力の言語を自動判定する機能はありません。`result.json` の `input_sign_language` は汎用の `unconfirmed; checkpoint is trained for ASL` という固定記録です。既存の自前入力がASLであることは別途ユーザー確認済みで、入力の管理記録と区別してください。

| 保存ファイル | 内容・確認点 |
|---|---|
| `prediction.txt` | 成功時の未補正の生成英文1行 |
| `result.json` | `status`、`exit_code`、英文、経過時間、設定、入力・重みSHA256、依存、上流revision、実ONNX provider |
| `inference.log` | 上流の標準出力・標準エラー。モデル読込、provider、失敗理由を確認 |
| `command.txt` | 実際の上流起動コマンド。作業ディレクトリと環境変数はJSON側に記録 |
| `environment.txt` | 実行時の `pip freeze` |

成功の目安は `status: "success"`、`exit_code: 0`、非空の `prediction.txt`、人物検出・姿勢推定の両セッションで `CUDAExecutionProvider` が記録されることです。CUDAとCPUの両方がprovider一覧に出る場合もあり、CPU表記だけでCUDAが無効とは判断しません。

上流プロセスが失敗した場合は `inference.log` と `result.json` を確認します。ただし入力不存在・重み不足・ハッシュ不一致など、出力先作成より前の検査で停止した場合には、これらの記録は作られません。

`elapsed_seconds` は上流子プロセスの起動から終了までで、import・姿勢抽出・モデル読込・生成を含みます。補助側のSHA256計算等を含むCLI全体の時間とは異なり、初回のONNX取得が発生すればその待ち時間も入ります。

`run_online.py` はposeをメモリ上で処理し、骨格ファイル・字幕付き動画・SRTは作りません。翻訳信頼度は提供されないため `translation_confidence: null` です。姿勢点のscoreは翻訳の信頼度ではありません。

## よくある問題と対処

| 症状 | 原因・確認箇所 |
|---|---|
| `No matching distribution found for torch==2.1.1+cu121` | 通常PyPIだけを参照している。環境構築の手順1で公式cu121のtorch一式を先に入れる |
| `conda: command not found` / activateできない | 利用中のシェルでcondaを使えるようにする。共有マシンなら `source /home/kosaki/anaconda3/etc/profile.d/conda.sh`。別マシンは自分のconda配置に合わせる |
| `No module named rtmlib` | 別Pythonを使っていないか確認し、同じ環境で同梱RTMLibをeditable installする |
| mT5の設定・tokenizer・重みが見つからない | 6ファイルの配置と `config.py` を確認。補助スクリプト経由で起動する |
| `MissingCUDAException: CUDA_HOME does not exist` | 初回はDeepSpeed import時に発生。修正済み `utils.py` と推論専用フラグを設定する `run_online.py` を使う |
| `libcurand.so.10` 等が見つからない / CUDA provider初期化失敗 | ORTがCUDA 12 feed版か、不足ライブラリ3点があるか確認。補助側の `LD_LIBRARY_PATH` 設定が必要 |
| ORTはimportできるがCPUだけで動く | provider候補一覧だけでなく実セッションを確認。現在の同梱RTMLibはCUDAが使えない場合に明示的に停止する |
| `FileExistsError` | 指定した `--output-dir` が既存。省略するか新しい保存先にする |
| checkpointのSHA256不一致 | 誤った重み、配布変更、不完全な取得を確認。期待ハッシュを書き換えて回避しない |
| `pip check` のDecord警告 | 前述の既知のwheelタグ不整合。import・動画読込とは区別する。他のエラーは個別に確認する |
| CUDA OOM / 長動画でメモリ増大 | 上流は全フレームを読み、16 workerで姿勢抽出する。256は翻訳入力の上限で、動画読込・姿勢抽出の上限ではない |
| 英文は出るが意味が違う | 推論成功だけでは翻訳の正しさを示さない。入力ASL、区間、画角、姿勢とモデル性能を分けて確認する |

256フレームを超える場合、姿勢抽出後に上流のランダムフレーム選択が入ります。長動画の自動文分割や連続字幕生成は実装・検証していません。同じseedでも抽出条件や演算精度によって文が変わった記録があります。

## 追加検証用スクリプトと過去の結果

通常の推論には `run_online.py` だけを使います。以下は過去の診断・評価を再現するための補助です。必要なmanifestや保存pose、入力ID等の前提があるため、各報告のコマンドと `--help` を確認してください。

| スクリプト | 用途 |
|---|---|
| [diagnose_online.py](scripts/diagnose_online.py) | 並列/逐次の姿勢抽出、保存pose、演算精度・系列への感度を診断 |
| [download_how2sign_subset.py](scripts/download_how2sign_subset.py) | How2Signの小規模評価用動画・配布pose・参照文を取得 |
| [evaluate_how2sign_subset.py](scripts/evaluate_how2sign_subset.py) | 同じ入力の配布poseと再抽出poseを比較 |
| [score_saved_results.py](scripts/score_saved_results.py) | 保存結果をBLEU/ROUGE/参考WERで採点 |
| [preprocess_self_videos.py](scripts/preprocess_self_videos.py) | 自前動画のcrop・縮小・余白条件とmanifestを作成 |
| [crop_vertical_black_bars.py](scripts/crop_vertical_black_bars.py) | 対象の縦動画にある黒帯を除去 |
| [evaluate_preprocessed_self.py](scripts/evaluate_preprocessed_self.py) | manifestに従う自前動画の推論・pose保存・採点 |
| [render_pose_overlays.py](scripts/render_pose_overlays.py) / [render_native_pose_overlays.py](scripts/render_native_pose_overlays.py) | 保存poseを映像へ重ねて可視化 |
| [analyze_temporal_attention.py](scripts/analyze_temporal_attention.py) | 保存結果からattention・部位特徴・介入を解析 |
| [visualize_temporal_attention.py](scripts/visualize_temporal_attention.py) | 上記解析の図と動画を作成 |

評価スクリプトの `script.txt` 読込は採点用です。単体推論の入力やモデルへのpromptとは異なります。可視化やposeの生データはローカルの `outputs/` へ保存します。

これまでの結論は、**GPU上で英文生成まで動くが、翻訳品質には課題があり、採用判断は保留**です。追加ASL動画07/08では質問・自己紹介に近い文が得られた一方、余分な語や名前の誤認が残りました。ほかの自前動画では意味の不一致が多く、画角を調整しただけでは正訳を確認できませんでした。

| 記録 | 内容 |
|---|---|
| [初回の自前2本・環境構築](reports/2026-09-12-how2sign-self-videos.md) | 依存追加、DeepSpeed失敗、CPUフォールバック、GPU再実行、ハッシュ |
| [翻訳不一致の調査](reports/2026-09-12-how2sign-mismatch-investigation.md) | 精度・姿勢・系列への感度。後から入力ASL・正解原稿をユーザー確認 |
| [撮影条件とHow2Signの比較](reports/2026-09-12-self-recorded-how2sign-compatibility.md) | 画角・人物配置などの検討 |
| [How2Sign test 12組](reports/2026-09-12-how2sign-test-subset.md) | 配布pose BLEU-4 14.96、同じ動画からの再抽出12.83。全testの再現ではない |
| [指標・例・自前との比較](reports/2026-09-12-score-examples-comparison.md) | 自前2本はBLEU-4 2.35、ROUGE-L 5.56。指標の解釈 |
| [自前01/02の前処理比較](reports/2026-09-12-self-preprocessing-evaluation.md) | 5条件×2本。正訳への改善は未確認 |
| [pose重ね合わせ動画](reports/2026-09-12-pose-overlay-videos.md) | 保存poseの可視化、動画一覧・凡例 |
| [自前03〜06の評価](reports/2026-09-12-self-03-06-evaluation.md) | 原動画と縦動画の黒帯除去比較 |
| [自前03〜06の前処理比較](reports/2026-09-12-self-03-06-preprocessing-comparison.md) | 5条件×4本、原画角の骨格動画 |
| [自前07/08の評価](reports/2026-09-12-self-07-08-pro-evaluation.md) | BLEU-4 22.59、ROUGE-L 28.57、参考WER 71.43%。正確な翻訳には未達 |
| [時間方向のattention解析](reports/2026-09-12-water-temporal-attention.md) | 保存poseでtoken IDまで再現し、注意・特徴・介入を分析。根本原因は未確定 |
| [3モデル比較](../reports/2026-09-12-pro-three-model-comparison.md) | 同じ07/08で比較。Uni-SignのCLI平均15.21秒/本、GPU観測ピーク13.17 GiB |

古い報告は当時の状態を残しています。「入力言語未確認」「上流checkoutはGit対象外」「ルートGitが無効」等の記載は、その後の入力確認・Git管理集約で更新されています。現在の運用はこのREADMEと共通ドキュメントを参照してください。

## 再現情報と参照先

| 項目 | 固定値・参照先 |
|---|---|
| 上流 | [ZechengLi19/Uni-Sign](https://github.com/ZechengLi19/Uni-Sign) |
| 取り込んだ上流revision | `eed438bcb49e30405cd6ccdfcccca330c134e830` |
| 取得元manifest | [research/upstream-sources.json](../../upstream-sources.json) |
| 取り込み時の差分 | [research/upstream-patches/sign--uni-sign--Uni-Sign.patch](../../upstream-patches/sign--uni-sign--Uni-Sign.patch) |
| Uni-Sign checkpoint | [How2Sign pose-only配布ページ](https://huggingface.co/ZechengLi19/Uni-Sign/blob/main/how2sign_pose_only_slt.pth)。当初のrevision未記録、SHA256で固定 |
| mT5 revision | [`2eb15465c5dd7f72a8f7984306ad05ebc3dd1e1f`](https://huggingface.co/google/mt5-base/tree/2eb15465c5dd7f72a8f7984306ad05ebc3dd1e1f) |
| 実行ごとの記録 | 各出力先の `result.json`、`command.txt`、`environment.txt`、`inference.log` |
| 除外された上流資材 | [research/upstream-local-assets.json](../../upstream-local-assets.json)。学習ラベル等はこの単体推論に不要 |

README再構成時には、ローカルに保存された2026-09-12のCodex会話（初期環境構築・単体推論の依頼と対処）も参照しました。チャット本文や個人環境の履歴ファイルをこのリポジトリへコピーせず、必要な手順を上記へ整理しています。環境構築の根拠は、共有可能な[初回実験記録](reports/2026-09-12-how2sign-self-videos.md)とローカルの `outputs/setup-20260912/` でも追えます。

利用条件の配布元表記は、[Uni-Signモデルカード](https://huggingface.co/ZechengLi19/Uni-Sign)がCC BY-NC 4.0、[mT5モデルカード](https://huggingface.co/google/mt5-base)がApache 2.0です。入力データ・姿勢検出モデルの利用条件は、それぞれの配布元を参照してください。

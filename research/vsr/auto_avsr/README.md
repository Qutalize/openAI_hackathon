# Auto-AVSR：英語動画の読唇を動かす

更新：2026-09-13。**音声トラックのない英語動画から、英語テキストを出すGPU推論**の手順をまとめる。日本語への翻訳や手話翻訳は行わない。

この環境は、2026-09-08のCodexとの構築チャット、実行ログ、[試運転記録](reports/2026-09-08-gpu-smoke.md)に基づく。上流のインストール例だけでは解決しなかった依存・キャッシュ・動画保存の問題を、自作スクリプトと固定依存に反映している。**再現には、このREADMEの `scripts/setup_uv.sh` と `requirements-uv.lock` を使う。condaやUSR2のインストールは不要。**

2026-09-08〜09日の公開LRS3 1本・自前動画6本・GRID 2本はGPU推論に成功している。実行成功と認識精度は別で、誤った英文を返す例もある。[チーム共有用まとめ](reports/2026-09-09-team-summary.md)に出力例と所感を記録した。

## 1. 作業場所と最短の再実行

以下のコマンドは、特記しない限り**外側の `research/vsr/auto_avsr/`** で実行する。

```bash
cd /mnt/kiso-qnap5/activities/260915_codex_hackathon/research/vsr/auto_avsr
```

別の場所へプロジェクトをcloneした場合は、この `cd` のパスを読み替える。内側の `auto_avsr/` は上流コードの置き場。

この共有環境には `.venv/`、重み、サンプルが配置済みなので、GPUを利用できるシェルから次で再実行できる。

```bash
bash scripts/run_vsr.sh outputs/setup/video_only.mp4 outputs/my-first-run
cat outputs/my-first-run/transcript.txt
cat outputs/my-first-run/result.json
```

**出力先は未作成の名前にする。** 失敗時も出力ディレクトリが残ることがあるため、再試行では `outputs/my-first-run-02` など別名を指定する。

初めて構築する場合は、次の順で進める。

1. [環境構築](#3-環境構築)：uvと専用 `.venv/` を準備する。
2. [重みと必要資材](#4-事前学習済み重みと必要資材)：重み・サンプル・Git対象外の付随ファイルを揃える。
3. 上記のサンプル推論を実行する。
4. [自分の動画を入力](#5-自分の動画を入力する)する。

## 2. どこに何があるか

```text
research/vsr/auto_avsr/              # このREADMEの作業ディレクトリ
├── README.md                       # この環境での準備・推論手順
├── requirements-uv.in              # 直接依存とバージョン
├── requirements-uv.lock            # 実行環境の全80パッケージを固定
├── downloads.sha256               # VSR重みと公開サンプルZIPのSHA256
├── artifacts.sha256               # 平均顔・tokenizer・検出器のSHA256
├── scripts/                        # このプロジェクトの実行補助
│   ├── setup_uv.sh                 # .venv作成、固定依存の同期、整合確認
│   ├── download.sh                 # 重み・サンプル取得とサンプル準備
│   ├── prepare_sample.py           # ZIPから1本展開し、音声を除去
│   ├── run_vsr.sh                  # 通常の推論入口
│   ├── infer.py                    # 検査→前処理→CUDA推論→結果保存
│   ├── temporal_ctc.py             # CTC系列確率・forced alignmentの解析補助
│   └── test_temporal_ctc.py        # 上記解析補助のテスト
├── auto_avsr/                      # 取り込み済みの上流コード
│   ├── lightning.py               # ModelModuleとデコード処理
│   ├── espnet/                    # encoder・decoder・beam searchなど
│   ├── datamodule/                # 映像変換・tokenizerなど
│   ├── preparation/               # 顔検出・位置合わせ・口領域切り出し
│   ├── spm/unigram/               # 語彙定義とSentencePieceモデル
│   └── tutorials/                 # 上流notebook：単体推論・口cropなど
├── reports/                       # Git管理する検証結果・所感
├── .venv/                         # このモデル専用Python環境（Git対象外）
├── weights/                       # VSR事前学習済み重み（Git対象外）
└── outputs/                       # 動画・生出力・ログ（Git対象外）
    ├── setup/                     # LRS3.zip、原本、無音声版、構築時ログ
    ├── 20260908-lrs3-gpu/          # 初回失敗時の出力先
    ├── 20260908-lrs3-gpu-retry/    # 公開LRS3の成功結果
    ├── self-recorded-gpu/         # 自前6本の25 fps版・推論・原稿比較
    ├── grid-domain-gpu/           # GRID 2本の入力・推論・評価
    ├── 20260912-temporal-06/       # 追加の時間方向解析
    └── 20260912-temporal-input-audit/ # 追加解析の入力確認
```

`temporal_ctc.py` は通常の `run_vsr.sh` から呼ばれない解析ライブラリ。正解文を与えるforced alignmentは、その文に拘束した時刻の仮説であり、自由な読唇結果や真の発話時刻ではない。

上流は [mpc001/auto_avsr](https://github.com/mpc001/auto_avsr/tree/182b62837773ab01052d4ac21ef1d2203ea7d267)、元revisionは `182b62837773ab01052d4ac21ef1d2203ea7d267`。取得元は [upstream-sources.json](../../upstream-sources.json) に記録している。

2026-09-12以降、**内側の `auto_avsr/` のコード・設定・文書もルートのGitで通常ファイルとして管理する**。モデル内で上流を再cloneしたり、`.git/` を作ったりする必要はない。重み・動画・顔ランドマーク・tokenizerの `.model` などは除外する。除外資材の一覧と復元元は [upstream-local-assets.json](../../upstream-local-assets.json)、経緯は [Git管理の集約](../../../docs/07-git-consolidation.md) を参照。

## 3. 環境構築

### 3.1 実行を確認した構成

Linux x86_64、Bash、NVIDIA GPUを使う。セットアップ・ダウンロードには外部ネットワーク、`curl`、`sha256sum` が必要。

| 項目 | 確認したバージョン・条件 |
|---|---|
| GPU | NVIDIA RTX A6000、VRAM 49140 MiB |
| NVIDIAドライバ | 590.48.01（2026-09-08実行時） |
| uv / Python | uv 0.12.10 / Python 3.10.21 |
| PyTorch / CUDAビルド | `torch==2.5.1+cu124` / CUDA 12.4 |
| torchvision / torchaudio | `0.20.1+cu124` / `2.5.1+cu124` |
| PyTorch Lightning | `2.5.0.post0` |
| MediaPipe / NumPy | `0.10.21` / `1.26.4` |
| OpenCV / scikit-image | `opencv-contrib-python==4.11.0.86` / `0.25.2` |
| PyAV / SentencePiece | `av==13.1.0` / `sentencepiece==0.2.0` |
| FFmpegバイナリ | `imageio-ffmpeg==0.6.0` 同梱版 |

全依存は [requirements-uv.lock](requirements-uv.lock)、直接依存は [requirements-uv.in](requirements-uv.in)。lockはバージョン固定の一覧で、配布wheelのハッシュまでは固定していない。他OS・GPU・CPUのみの構成は未検証。CUDA 12.4版PyTorchを実行できるドライバが必要で、この手順にCUDA Toolkitの手動インストールは含まれない。

初回構築時の `.venv/` は約5.1 GiBだった。重み約1 GBに加え、Python本体・ダウンロードキャッシュ・入力動画・出力の空き容量も用意する。

### 3.2 uvを用意する

この共有環境では次のuvを使った。通常のPATH上の `uv` とは限らない。

```bash
/tmp/usr2-bootstrap/bin/uv --version
export UV_BIN=/tmp/usr2-bootstrap/bin/uv
```

別環境で `uv` がPATHにあれば `export UV_BIN=uv` とする。未導入の場合は [uv公式インストール手順](https://docs.astral.sh/uv/getting-started/installation/)に従う。Linuxでの導入例：

```bash
curl -LsSf https://astral.sh/uv/install.sh -o /tmp/auto-avsr-install-uv.sh
sh /tmp/auto-avsr-install-uv.sh
export UV_BIN="$HOME/.local/bin/uv"
"$UV_BIN" --version
```

この導入例は最新版uvを取得する。過去の実行で確認したuvは0.12.10であり、上記インストーラーによる新規導入は今回再実行していない。

### 3.3 モデル専用環境を作る

同じシェルで、外側の `research/vsr/auto_avsr/` から実行する。

```bash
export UV_CACHE_DIR=/tmp/auto-avsr-uv-cache
# 新しく取得するPython本体を、/tmp以外の永続領域に保存する
export UV_PYTHON_INSTALL_DIR="$HOME/.local/share/uv/python"
bash scripts/setup_uv.sh
```

`UV_PYTHON_INSTALL_DIR` は自分が書き込める永続ディレクトリへ変更できる。指定しない場合、スクリプトの既定は `/tmp/auto-avsr-uv-cache/python`。そこにPythonが取得されると、後日の `/tmp` 清掃で `.venv/bin/python` の参照先が消える可能性がある。

[setup_uv.sh](scripts/setup_uv.sh) は次を行う。

1. `.venv/bin/python` がなければ `uv venv --python 3.10` で作成する。利用可能なPython 3.10を探し、必要なら取得する。
2. `uv pip sync` で `requirements-uv.lock` の80パッケージへ同期する。既存 `.venv/` に対しても同期するため、このモデル専用の環境として扱う。
3. CUDA 12.4のPyTorch配布indexを指定し、`uv pip check` で依存整合を検査する。

キャッシュの既定値は `/tmp/auto-avsr-uv-cache`、リンク方式は `UV_LINK_MODE=copy` に固定し、このNFS上の環境に合わせている。activateは不要で、以後の補助スクリプトは `.venv/bin/python` を直接使う。

初回は既存USR2環境からPython 3.10.21のインタープリターを利用して `.venv/` を作った。**USR2のsite-packagesは共有していない**。現在のPython実体は `/home/kosaki/.local/share/uv/python/cpython-3.10-linux-x86_64-gnu/bin/python3.10` で、`include-system-site-packages = false`。この個人パスを新規環境で再現する必要はない。

なお、スクリプトの作成指定は `3.10` であり、パッチ版 `3.10.21` まで自動固定するものではない。既存 `.venv/` のPythonバージョンも自動変更しない。

### 3.4 環境を確認する

```bash
.venv/bin/python --version
"$UV_BIN" pip check --python .venv/bin/python
nvidia-smi
.venv/bin/python -c 'import torch; print("torch:", torch.__version__); print("CUDA build:", torch.version.cuda); print("CUDA available:", torch.cuda.is_available()); print("GPU:", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "unavailable")'
.venv/bin/python -c 'import av, mediapipe as mp, imageio_ffmpeg; print("PyAV:", av.__version__); print("MediaPipe:", mp.__version__); print("solutions:", hasattr(mp, "solutions")); print("FFmpeg:", imageio_ffmpeg.get_ffmpeg_exe())'
```

`CUDA available: True` と `solutions: True` を確認する。補助スクリプトはCUDAが利用できない場合に停止し、CPUへ切り替わらない。初回はCodexサンドボックス内からGPU・外部DNSへアクセスできず、許可されたサンドボックス外実行で構築・推論に成功した。通常の端末でも、実際に推論するシェルから確認する。

## 4. 事前学習済み重みと必要資材

### 4.1 どの重みを選ぶか

**まず `vsr_trlrs2lrs3vox2avsp_base.pth` を1つ取得する。** このプロジェクトの既定値で、記録したGPU推論はすべてこの重みを使っている。

| 上流の重み | 選択の目安 | 上流公表LRS3 WER |
|---|---|---:|
| `vsr_trlrs2lrs3vox2avsp_base.pth` | 今回の再現用。LRS2・LRS3・VoxCeleb2・AVSpeechで学習 | 20.3% |
| `vsr_trlrs3vox2_base.pth` | 学習データの異なるVSR。ここでは未検証 | 24.6% |
| `vsr_trlrs3_base.pth` | LRS3で学習したVSR。ここでは未検証 | 36.0% |
| `vsr_trlrs3_23h_base.pth` | 上流が学習初期段階に使う重みとして説明。初回推論には選ばない | 93.0% |
| `asr_*.pth` | 音声入力のASR用。この映像専用CLIには使わない | — |

出典：[固定revisionの上流Model zoo](https://github.com/mpc001/auto_avsr/tree/182b62837773ab01052d4ac21ef1d2203ea7d267#model-zoo)。公表WERは上流の評価条件の値で、自前動画での精度ではない。

選択する重みの取得元は [Google Drive](https://drive.google.com/file/d/1r1kx7l9sWnDOCnaFHIGvOtzuhFyFA88_/view)。保存先は `weights/vsr_trlrs2lrs3vox2avsp_base.pth`、サイズは **1,001,892,616 bytes（約1.00 GB）**、SHA256は次のとおり。

```text
fbf7cd70ff1c0e694b3030fb779dbb4570f04e4b841d62f9296c229e94878ddb
```

### 4.2 重みと動作確認用サンプルを取得する

環境構築後に実行する。

```bash
bash scripts/download.sh
```

[download.sh](scripts/download.sh) は次を行う。

- `.venv/bin/gdown` で上記の重みを取得する。
- LipVoicerが公開するLRS3サンプルZIP（24,436,327 bytes、約24.4 MB）を固定revisionのURLから取得する。
- `sha256sum -c downloads.sha256` で重みとZIPを検証する。既存ファイルも検証し、不一致なら停止する。
- `prepare_sample.py` でZIP内の `LRS3/good/NqOjj1FCcVY_00007_gt.mp4` だけを展開し、映像トラックをコピーして音声を除去する。

`outputs/setup/` に `LRS3.zip`、音声付き `original.mp4`、25 fps・音声なしの `video_only.mp4`、取得元とハッシュを記録した `input_manifest.json` ができる。再実行では既存の重みとZIPの取得を省略するが、サンプル原本・無音声版・manifestは再生成する。このサンプルは元から25 fpsで、準備スクリプト自体はFPS変換をしない。

全LRS2/LRS3データセット、学習用ラベル、18 GBの事前計算ランドマークは、動画1本の推論には不要。

重みだけを取得して自分の動画を使う場合は、空の `weights/` に対して次を実行する（サンプルは取得しない）。

```bash
mkdir -p weights
.venv/bin/gdown 1r1kx7l9sWnDOCnaFHIGvOtzuhFyFA88_ \
  -O weights/vsr_trlrs2lrs3vox2avsp_base.pth --no-cookies
rg '  weights/' downloads.sha256 | sha256sum -c -
```

この重みだけの例では `rg` が必要。通常は `download.sh` を使えばよい。

### 4.3 新規cloneで不足する平均顔・tokenizerを復元する

**`download.sh` は以下の2ファイルを取得しない。** この共有環境には残っているが、Git対象外のため新規cloneには含まれない。固定revisionの上流から、コードが参照する元の場所へ取得する。

```bash
UPSTREAM_REV=182b62837773ab01052d4ac21ef1d2203ea7d267
for asset in \
  preparation/detectors/mediapipe/20words_mean_face.npy \
  spm/unigram/unigram5000.model
do
  if [ ! -f "auto_avsr/$asset" ]; then
    curl -fL --retry 2 \
      "https://raw.githubusercontent.com/mpc001/auto_avsr/$UPSTREAM_REV/$asset" \
      -o "auto_avsr/$asset"
  fi
done
sha256sum -c artifacts.sha256
```

このコマンドは新規clone用に追記した復元手順。今回、既存資材のSHA256一致は確認したが、空のcloneからの構築全体は再実行していない。

| 資材 | 用途・準備方法 |
|---|---|
| `auto_avsr/preparation/detectors/mediapipe/20words_mean_face.npy` | 顔の位置合わせに使う平均顔。上記で復元 |
| `auto_avsr/spm/unigram/unigram5000.model` | 英語SentencePieceモデル。上記で復元 |
| `auto_avsr/spm/unigram/unigram5000_units.txt` | 出力tokenの語彙定義。Git管理済み |
| `.venv/.../mediapipe/modules/face_detection/*.tflite` | 顔検出器。固定版MediaPipeパッケージに同梱 |

`artifacts.sha256` は表の平均顔・tokenizer・語彙と、MediaPipeの顔検出器2件を検証する。今回のMediaPipe経路では、RetinaFaceの重みや別の `face_landmarker.task` は取得しない。

## 5. 自分の動画を入力する

### 5.1 音声を除去し25 fpsへ変換する

入力は顔・口元が見える短い英語動画とし、まず1人が映る正面の動画で確認する。音声付き原本はそのまま保存し、モデル専用の変換結果を `outputs/` へ置く。

この環境ではシステムの `ffmpeg` が見つからなかったため、同梱バイナリを使う。プロジェクトに配置済みの自前動画を変換する例：

```bash
mkdir -p outputs/my-input
FFMPEG_BIN="$(.venv/bin/python -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())')"
"$FFMPEG_BIN" -nostdin -n \
  -i ../../../data/vsr/06_work_update/video_only.mp4 \
  -map 0:v:0 -vf fps=25 -an -c:v libx264 -crf 18 -preset fast \
  outputs/my-input/video_25fps.mp4
```

`-i` は自分の原本パスへ変更できる。`video_only.mp4` という名前でも25 fpsとは限らない。`-n` は既存の出力を上書きしない指定で、再変換する場合は保存先の名前を変える。

### 5.2 推論する

```bash
bash scripts/run_vsr.sh outputs/my-input/video_25fps.mp4 outputs/my-video-run
```

利用可能な引数は次だけ。

```text
bash scripts/run_vsr.sh VIDEO OUTPUT [--weights WEIGHTS]
```

| 引数 | 意味 |
|---|---|
| `VIDEO` | 音声トラックなし・25 fpsの動画。音声付きやFPS差が0.01を超える入力は拒否 |
| `OUTPUT` | 未作成の出力ディレクトリ。親ディレクトリは自動作成 |
| `--weights` | 省略時はこのモデル配下の `weights/vsr_trlrs2lrs3vox2avsp_base.pth` |
| `--help` | 引数の確認。GPU推論は開始しない |

入力・出力・明示した重みの相対パスは、**コマンドを実行する現在のディレクトリ基準**。既定の重みとPython環境はスクリプト自身の場所から解決する。内側の上流ディレクトリから実行する場合は次のようになる。

```bash
cd auto_avsr
bash ../scripts/run_vsr.sh ../outputs/setup/video_only.mp4 ../outputs/from-upstream-run
cd ..
```

処理の流れは、動画全体の読込 → CPUのMediaPipeで顔検出 → 欠落フレームの補間・平均顔への位置合わせ → 96×96の口領域切り出し → 88×88中心crop・グレースケール・正規化（0〜1化、平均0.421・標準偏差0.165）→ CUDA上のモデル・beam search → 英語文の保存。

モデルと入力は `cuda:0` に配置し、CPU側のスレッド数は8。beam size 40、CTC weight 0.1は上流既定を使う。これらを変更するCLI引数はない。外部言語モデル・LLM文章補正・翻訳・正解文の入力は加えていない。

動画全体をメモリに読み込む方式で、長動画の自動分割・複数話者の指定・ストリーミングは実装していない。

## 6. 出力の見方

| ファイル | 内容 |
|---|---|
| `transcript.txt` | 未補正の英語認識文 |
| `result.json` | 認識文、入力・重みのパス、入力SHA256、前処理・GPU情報、時間・メモリ |
| `mouth_crop.mp4` | モデル入力前の96×96口領域動画。88×88正規化後のテンソルとは別 |

`result.json` の主な項目：

- `input_language` / `output_language` はともに `en`、`modality` は `video`。
- `frames`、`fps`、`duration_seconds`、`input_shape` で入力を確認する。
- `detected_frames` は補間前に顔を検出できたフレーム数。認識の正しさを示す値ではない。
- `model_device`、`gpu`、`torch`、`cuda` で実行環境を確認する。
- `import_and_preprocess_seconds`、`model_load_seconds`、`inference_seconds` と、その合計 `total_seconds` を記録する。
- `peak_allocated_mib` / `peak_reserved_mib` はPyTorchのピーク割当／予約量。GPUプロセス全体の使用量ではない。
- `confidence` は確率値が未提供なので `null`。CTCの解析スコアを認識正答率として補わない。

時間はCUDA同期付きで測る。合計にはimport・動画読込・前処理・crop保存・モデル読込・GPU転送・推論を含み、事前の25 fps変換、Python起動前、入力SHA256計算、結果保存は含まない。各実行でモデルを読み直す。

標準出力にも結果JSONが出る。ログを残す場合は、推論の出力先ディレクトリを先に作らず、例えばコマンド末尾に `> outputs/my-video-run.log 2>&1` を付ける。重みSHA256や上流revisionは結果JSONに自動保存されないため、実験記録には重みSHA256を `downloads.sha256`、上流revisionを `../../upstream-sources.json` から併記する。

## 7. 上流手順から調整した点・トラブル対処

[上流README](auto_avsr/README.md)のSetupとModel zoo、`tutorials/inference.ipynb` のvideo経路を基にした。2026-09-08の構築チャットと [GPU試運転記録](reports/2026-09-08-gpu-smoke.md)で確認した変更は以下のとおり。上流Pythonコードへのパッチ適用は不要で、調整は親ディレクトリの依存定義・補助スクリプトにある。

| 問題・条件 | この環境での対応 |
|---|---|
| 既定のuvキャッシュに書き込めない | `UV_CACHE_DIR=/tmp/auto-avsr-uv-cache` を指定。単独の `uv pip check` でも同じ設定を使う |
| NFS上に専用環境を配置 | `UV_LINK_MODE=copy` を指定して80パッケージの配置に成功 |
| PyAV 14.4.0がソースビルドになり、FFmpeg開発ライブラリ不足で失敗 | wheelを利用できた `av==13.1.0` に固定 |
| 上流検出器が旧 `mp.solutions` APIを使用 | 動作確認した `mediapipe==0.10.21` に固定。バージョン無指定で上書きしない |
| システム版FFmpegがない | `imageio-ffmpeg==0.6.0` 同梱実行ファイルを利用。`ffmpeg-python` だけでは実行ファイルは用意されない |
| 上流tutorialのデモURLがHTTPSで404 | 別の公開元であるLipVoicerのLRS3サンプルへ切り替え |
| 初回推論で `AttributeError: 'numpy.float64' object has no attribute 'numerator'` | `infer.py` の動画保存に整数FPS `round(fps)` を渡すよう修正済み |
| サンドボックスでCUDAや外部DNSが使えない | GPU・ネットワークへアクセスできる実行環境で確認。過去は承認済みの制限外実行で成功 |
| 新規cloneで `.npy` / `.model` が見つからない | 4.3の2資材を復元して `artifacts.sha256` を照合 |
| `FileExistsError` | 出力先を未作成の別名へ変更。失敗後の同じ名前も再利用しない |
| 音声トラック・25 fpsの検査で停止 | 5.1の変換を行い、変換済み動画を入力 |
| `Cannot detect any frames in the video` | 顔・口元が見える動画か確認。1フレームも顔を検出できなければ停止する。一部の未検出は補間する |
| SHA256不一致 | 推論せず、保存先・取得元・ダウンロード完了を確認。既存ファイルがあると `download.sh` は再取得しない |

依存を戻す際は `setup_uv.sh` でlockへ同期する。PyAVのビルド失敗や動画保存のエラーを、GPUやモデルの精度問題と混同しない。

## 8. 検証済みの範囲と記録

| 検証 | 実行成否 | 認識結果・制約 | 記録 |
|---|---|---|---|
| 公開LRS3サンプル1本 | GPU推論成功 | 正解21語中1語誤り、WER 4.76%。選ばれた1本の結果 | [GPU試運転](reports/2026-09-08-gpu-smoke.md) |
| 自前動画6本 | 6/6成功 | 原稿との単語誤り率56.32%。原稿と実発話の一致は未確認 | [自前動画の記録](reports/2026-09-08-self-recorded-gpu.md) |
| GRID公式サンプル2本 | 2/2成功 | 公式正解に対する合計WER 50%（6/12語） | [別ドメイン検証](reports/2026-09-09-grid-domain-gpu.md) |

公開LRS3の5.8秒動画では、推論8.92秒、スクリプト内合計20.00秒、PyTorchピーク割当約1.20 GiB。各動画1回の値で、厳密に揃えたcold/warm測定ではない。他GPUの必要VRAM、長動画、無発声口パク、リアルタイム性能は未確認。モデル比較は同じ入力・条件を揃えて別途行う。

2026-09-13のREADME改訂では、過去の構築チャット・コード・実行記録を照合し、現存環境のPythonと主要依存、80パッケージの `uv pip check`、推論CLIの `--help`、`downloads.sha256`・`artifacts.sha256` の一致を確認した。**新規環境の全再構築とGPU推論は今回再実行していない。**

コードのライセンスは [Apache 2.0](auto_avsr/LICENSE)。上流は、事前学習済みモデルには学習データ由来の別条件があり得ると記載している。重みとサンプルの個別利用条件には未確認の部分がある。現在の重み・動画・生出力はローカル検証用に保存し、Gitには追加しない。

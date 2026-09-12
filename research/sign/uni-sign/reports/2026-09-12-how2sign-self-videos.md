# Uni-Sign / How2Sign：自前動画2本の試運転

## 結論

2026-09-12、How2Sign pose-onlyの学習済み重みで動画2本から未補正の英文を生成した。
実行は成功し、姿勢検出の両ONNXセッションで`CUDAExecutionProvider`、翻訳でPyTorch CUDA/BF16を確認。
重みのstrict読み込みでMissing/Unexpected keysは空だった。追加学習は一切行っていない。

生成内容は両方とも暫定原稿と一致せず、実用的な翻訳品質を確認したとはいえない。
動画の手話言語・実際の表現内容は入力README上も未確認であり、次にASLとの適合性を確認する必要がある。

| 入力ID | フレーム数 | 上流プロセス経過時間 | 実行 | 暫定原稿との一致 |
|---|---:|---:|---|---|
| `01_whats_your_name` | 121 | 13.76秒 | 成功 | 不一致 |
| `02_greetings` | 155 | 14.56秒 | 成功 | 不一致 |

経過時間は上流子プロセスの起動直前から終了まで。import、姿勢抽出、mT5とcheckpoint読み込み、英文生成を含む。
依存インストール・mT5ダウンロード・前後のSHA256計算は含めない。上記2回では姿勢モデルはキャッシュ済み。
各入力1回の計測でありwarm latencyの統計やp50/p95ではない。
上流が表示したPyTorch最大メモリは2600MiBだが、ONNX Runtimeの割当を含むGPU全体のピークではない。
終了後GPUは21MiB使用、利用率0%へ戻った。

生の英文は各ローカル出力の`prediction.txt`を参照する。Git管理用のこの報告には認識内容の匿名要約のみを記載する。
独自decoder・LLM補正・語彙制限・正解文のprompt投入は行っていない。
翻訳の信頼度は未提供。姿勢検出scoreを翻訳信頼度として扱っていない。

## 実行コマンドと結果配置

作業ディレクトリ：プロジェクトルート。

```bash
conda run --no-capture-output -n Uni-Sign python -B \
  research/sign/uni-sign/scripts/run_online.py \
  data/sign/01_whats_your_name/original.mp4 \
  --output-dir research/sign/uni-sign/Uni-Sign/outputs/20260912-how2sign-01-whats-your-name-gpu

conda run --no-capture-output -n Uni-Sign python -B \
  research/sign/uni-sign/scripts/run_online.py \
  data/sign/02_greetings/original.mp4 \
  --output-dir research/sign/uni-sign/Uni-Sign/outputs/20260912-how2sign-02-greetings-gpu
```

上記は実際に実行したコマンド。保存先は既に存在するので、そのまま再実行すると上書きを拒否する。
再実行時は`--output-dir`を省略して新規保存先を自動生成するか、別の新規ディレクトリを指定する。
各保存先に`prediction.txt`、`inference.log`、`result.json`、`command.txt`、`environment.txt`がある。
`result.json`には上流コマンド、環境変数、ローカルパッチ、依存一覧と各重みのSHA256も記録した。

## 出所・環境・前処理

- 上流：[GitHub](https://github.com/ZechengLi19/Uni-Sign)、revision `eed438bcb49e30405cd6ccdfcccca330c134e830`。
- 使用重み：[how2sign_pose_only_slt.pth](https://huggingface.co/ZechengLi19/Uni-Sign/blob/main/how2sign_pose_only_slt.pth)。
  SHA256 `1bfd5f3312f04e4736f0a52f4ef9535916e6de9676a2a0d00c708748683fb00d`は配布元表示と一致。
  元のダウンロードrevisionは未記録だが、今回使用したファイルの内容はこのSHA256で固定。
- mT5：[google/mt5-base](https://huggingface.co/google/mt5-base/tree/2eb15465c5dd7f72a8f7984306ad05ebc3dd1e1f)、revision `2eb15465c5dd7f72a8f7984306ad05ebc3dd1e1f`。
  `pytorch_model.bin` SHA256 `180573b534144580f04af026da62bf71bc976ee1b7eb311b8945e2fefde8d614`。
- checkpointのモデルカード表記：CC BY-NC 4.0。mT5表記：Apache 2.0。一般の再配布・商用利用を承認した記録ではない。
- Ubuntu 24.04.3 LTS、NVIDIA RTX A6000 49140MiB、ドライバ590.48.01。
- conda環境`Uni-Sign`、Python 3.9.25、torch 2.1.1+cu121、CUDA runtime 12.1、cuDNN 8902、BF16対応。
- torchvision 0.16.1+cu121、torchaudio 2.1.1+cu121、Transformers 4.40.0、NumPy 1.22.4、OpenCV 4.6.0.66。
- 今回追加：rtmlib 0.0.13（同梱コードのeditable install）、onnxruntime-gpu 1.18.0（公式CUDA 12 feed）、coloredlogs 15.0.1、humanfriendly 10.0。
  nvidia-curand-cu12 10.3.2.106、nvidia-cufft-cu12 11.0.2.54、nvidia-cuda-runtime-cu12 12.1.105。
  インストール前後のfreeze比較で既存項目の削除・更新なし。
- 入力：1920×1080、OpenCVの報告fpsは約30.245 / 30.308。元動画を再エンコード・回転・cropし直していない。
- 入力SHA256：
  - `01_whats_your_name`: `f219c03cc769747427a700b935d5d3e78b9705f1e9b661489213af33f853ed10`
  - `02_greetings`: `14a4992d7d626131026a3c8997739f6cce977822eb3d02b4b318e69ceef36d0d`
- 手話言語・撮影条件・実際の正解文・同意の詳細は入力READMEの管理情報を参照。本文からASLと確定しない。
- 前処理は[上流online_inference.py](https://github.com/ZechengLi19/Uni-Sign/blob/main/demo/online_inference.py)を維持：
  Wholebody lightweight、ONNX Runtime、COCO wholebody 133点、16 worker、x/幅・y/高さ正規化、上流の部位別正規化。
  pose-only、max_length 256、seed 42。両動画は256以下のためランダムフレーム選択なし。
  英文生成はBF16、num_beams 4、max_new_tokens 100。音声・原稿・事前作成pose_formatは不使用。
- 姿勢モデルSHA256：
  - YOLOX tiny ONNX: `ceb11c07298f95c50d7c5abeb906d03340c85f23aa79e3e66966e7fb6c307250`
  - RTMW lightweight ONNX: `68db326c5c6f3273456f803eae0faf5440478369f2c3ee67258d2f36512e8d76`
  配布URLは同梱`wholebody.py`内のOpenMMLab URL、取得ログは初回retry1の`inference.log`に保存。

## 問題と対処

1. mT5が未配置：必要なPyTorch重みとtokenizerファイルのみ取得し、`config.py`の先頭を`./weights/mt5-base`へ変更。
2. RTMLib/ONNX Runtime未導入：同梱RTMLibとCUDA 12・cuDNN 8版ORT 1.18.0を追加。
   [ORT公式互換表](https://onnxruntime.ai/docs/execution-providers/CUDA-ExecutionProvider.html#requirements)と[公式配布案内](https://onnxruntime.ai/docs/install/)を確認した。
3. 初回はDeepSpeed 0.16.3 import時の`MissingCUDAException: CUDA_HOME does not exist`で停止。
   原因はFPQuantizer互換チェックが`nvcc`を要求すること。
   [DeepSpeed v0.16.3コード](https://raw.githubusercontent.com/deepspeedai/DeepSpeed/v0.16.3/op_builder/fp_quantizer.py)と[公式issue](https://github.com/deepspeedai/DeepSpeed/issues/5497)に対応する経路を確認。
   単体推論ではDeepSpeed関数を使わないため、`UNI_SIGN_INFERENCE_ONLY=1`時だけDeepSpeed importを省いた。
   フラグ未設定時は元のimportを維持。学習経路は今回未検証。
4. retry1はORTで`libcurand.so.10`不足が発生し、姿勢推定のみCPUへフォールバックして英文生成まで成功。
   この混合CPU/GPU実行は正式なGPU結果とは分けて保存した。
   CUDA 12.1向けの不足ライブラリ3点を追加し、保存補助がtorch/libとnvidia/*/libを`LD_LIBRARY_PATH`へ設定。
   同梱RTMLibへ実provider表示とCUDA不在時の明示エラーを追加して、上記2本をGPUで再実行した。
5. `pip check`はDecordの内部wheelタグが`cp36-cp36m`のため非ゼロ終了。
   確認したPythonは3.9で、Decord import・VideoReaderの121フレーム取得・先頭画像読み込みは成功。
   メタデータの矛盾自体は未修正で残す。依存チェックが全て成功したとは記載しない。

初回失敗・混合CPU/GPU試行の保存先も削除せず残した：
`outputs/20260912-how2sign-01-whats-your-name/`、`outputs/20260912-how2sign-01-whats-your-name-retry1/`。
セットアップ前後の環境とpip check結果は`outputs/setup-20260912/`。

## 検証と残課題

- 修正ファイルのPython構文、上流`git diff --check`、記録した3パッチのreverse apply checkが成功。
- 両GPU結果のexit code 0、status success、2つのONNX sessionでCUDA provider存在、prediction.txtとJSONの英文一致を確認。
- 重みを再保存・更新していない。入力ハッシュは入力READMEの値と一致。
- 既存のpycache変更は作業開始前から存在し、上書き・復元していない。今回のPython推論は`-B`で実行。
- 自作の保存補助・3つのパッチ・この記録を追加。モデル本体や前処理の認識ロジックは変更しない。
  上流checkoutと重み・出力を誤ってGitへ追加しないよう、ルート.gitignoreへ既存Uni-Sign配置を追加。
  共有ルートのGitメタデータが無効なため、commit/stageは実施していない。
- 精度指標、大規模評価、別checkpoint比較、長動画、ピークVRAM全体、再実行時の英文変動は未測定。
- 次の安全な確認は入力がASLかと撮影条件の照合。学習なしの改善候補として同一入力でOpenASL checkpoint比較は可能だが、今回は取得・実行していない。
- 所感：環境再現には追加の依存とimport回避が必要だった。生成英文の存在だけでは、挨拶・名前の質問などの自前用途に採用できるとは判断できない。現段階では保留。

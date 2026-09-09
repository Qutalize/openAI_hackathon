# USR 2.0：英語VSR（Lip reading only）

**状態：Hugeの取得とRTX A6000でのGPU推論に成功（2026-09-08）。**
[実測・同一入力比較](reports/2026-09-08-huge-gpu.md)：自前06ではピークallocated約35.11 GiB、
44.99秒、WERはBase+ 61.1% → Huge 55.6%（1本のみ、誤認はなお多い）。

現在の既定モデルはfine-tuned **Huge / high-resource / LRS2+LRS3+Vox2+AVS**。
入力は英語の発話映像、出力は英語テキスト。`modality=v`でGPU推論する。
GPUが利用できない場合はエラー終了する。MediaPipeの顔ランドマーク処理はCPUを使用する。

上流：[ahaliassos/usr2](https://github.com/ahaliassos/usr2)。
revision：`df0c78b7a3807e625a0fcdadd14b1cf674d21c91`（`upstream/`、コード変更なし）。
上流の高リソース表のVSR値はBase+ 24.8%、Huge 17.6%だが、自前動画での改善は別途評価する。
翻訳や独自LLMによる文章補正は行わない。

## GPU環境の構築

作業ディレクトリはこのREADMEのある`research/vsr/usr2/`。

```bash
# 新規作業場所でのみ実行
git clone https://github.com/ahaliassos/usr2.git upstream
git -C upstream checkout df0c78b7a3807e625a0fcdadd14b1cf674d21c91
# uvがPATHにある環境
bash scripts/setup_gpu.sh
```

既定の専用環境は`~/.virtualenvs/usr2-vsr-gpu`。`USR2_VENV`で変更可能。
共有NFSのインストール問題を避け、ローカルディスクへ分離する。
今回uvは`python3 -m pip install --target /tmp/usr2-bootstrap uv`で取得し、
`UV_BIN=/tmp/usr2-bootstrap/bin/uv bash scripts/setup_gpu.sh`を実行した。
uv本体が/tmpから消えた場合は再取得する。推論時にuvは不要。

Python 3.10.21、torch 2.5.1+cu124、torchvision 0.20.1+cu124、torchaudio 2.5.1+cu124。
MediaPipe 0.10.21、NumPy 1.26.4、PyAV 13.1.0。全81パッケージは
`requirements-gpu.lock`に固定し、セットアップ時に依存整合性とCUDA利用可否を検査する。
このマシンにFFmpeg CLIはなく、無音入力の検査・読込はPyAVのライブラリを利用する。
音声除去が必要な場合はFFmpeg等で事前に行う。

## Huge重みの取得

文章認識用の[公式fine-tuned Huge配布先](https://drive.google.com/file/d/1LzFOTYu45zCLOHGVLQt7pMGjw6jmmo9Y/view)。
encoder-onlyのself-supervised Hugeとは異なる。

```bash
bash scripts/download_huge.sh
```

取得実サイズは7,597,175,714 bytes（約7.08 GiB）。重みと前処理資材のSHA256は`artifacts.sha256`に記録する。
既存のBase+重みも保持する。コードのLICENSEはCC BY-NC 4.0。重み固有の追加条件は未確認。
重み、動画、顔ランドマーク、生ログ、口領域動画はGit対象外。

## 動画1本のGPU実行

```bash
bash scripts/run_vsr.sh /absolute/path/to/silent-english-video.mp4 outputs/my-huge-run
```

既定：Huge、CUDA、MediaPipe、beam size 20、CTC weight 0.1、CPUスレッド数8。
`USR2_BEAM_SIZE`と`USR2_NUM_THREADS`で調整可能。GPUの選択は`CUDA_VISIBLE_DEVICES`で行う。
過去のBase+試験で長い動画のbeam 40が24 GB GPUでOOMとなったため、既定beamは20。
長さ・beam幅によりVRAM使用量が増えるため、実測値は入力条件と合わせて参照する。

`run_vsr.sh`は入力に音声トラックがあると停止する。`run_gpu_demo.py`はCUDAを検査し、
上流`demo.py`を同一プロセスで実行する。上流のencoderとbeam searchがCUDAを使用する。
新しい出力先を指定すること。同名の出力先ではログ等が上書きされる。
`console.log`、`demo.log`、`time.txt`、`.hydra/`、`mouth_crop.mp4`、
`gpu_metrics.json`（PyTorchのピークallocated/reserved bytes）が出力先に残る。
VRAM値は当該プロセスのPyTorch allocator分であり、GPU全体の使用量ではない。

Base+との同一設定比較には`USR2_MODEL_SIZE=baseplus bash scripts/run_vsr.sh ...`を使用する。
過去の[CPU試運転](reports/2026-09-08-lrs3-smoke.md)および
[Base+・自前6本GPU試験](reports/2026-09-08-data-vsr-01-06-gpu.md)は当時の設定記録。
CPU用の`setup_uv.sh`と`requirements-uv.lock`は保持するが、現在の`run_vsr.sh`はGPU必須。
旧`.venv`リンクはこのマシンではリンク切れで、現在のスクリプトは参照しない。

前処理は25 fpsへの調整、顔ランドマーク検出、平均顔へのアフィン整列、96×96の口領域切り出し、
88×88の中央crop、グレースケール、`/255`、平均0.421・標準偏差0.165での正規化。
上流は動画読込時に音声も扱うが、`modality=v`では音声をencoderへ入力しない。
今回の入力には音声がない。

推論結果はモデルの英語文字列。信頼度の確率値は上流demoから提供されない。
正解文が未確認の動画では、文章が出たことと認識内容が正しいことを区別する。

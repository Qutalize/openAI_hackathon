# Auto-AVSR：uv環境とGPU試運転

2026-09-12 Git管理更新：既存の上流コード・設定・文書をルートのGitへ集約しました。
この作業ツリーでは上流コードは配置済みで、以下の過去の準備例にある上流への `git clone`・`git checkout`・パッチの再適用は不要です。
動画・重み・生出力は引き続きローカル管理です。上流ディレクトリ全体をGit対象外とする従来の記述は、この方針で置き換えます。
取得元revision、除外資材の準備、復元方法は [Git管理の集約](../../../docs/07-git-consolidation.md) を参照してください。

2026-09-08（JST）、英語の無音声動画から英語テキストへの**GPU推論成功**。
condaは不要。詳細は[試運転記録](reports/2026-09-08-gpu-smoke.md)。

チームへの短い共有には、実際の「正解／原稿」とモデルの生出力、速度、採用所感を1ページにした[チーム共有用まとめ](reports/2026-09-09-team-summary.md)を参照。

自前動画6本もGPU推論成功。原稿との単語誤り率は合計56.32%で、内容の取り違えが目立つ。
実発話を検証した正解文での精度ではない。詳細と再実行例は[自前動画の記録](reports/2026-09-08-self-recorded-gpu.md)。

学習元とは異なる収録ドメインのGRID公式英語動画2本でもGPU推論成功。
公式正解に対するWERは合計50%（6/12語）。[別ドメイン検証の結果と制約](reports/2026-09-09-grid-domain-gpu.md)。

## 配置

指定済みの `auto_avsr/` が上流checkout。ユーザー指定の配置を維持し、移動・変更していない。
自作補助・依存定義・報告をその親 `research/vsr/auto_avsr/` に集約した。
上流checkout、`.venv/`、`weights/`、`outputs/` はGit対象外。

## すぐに再実行

指定された上流ディレクトリから実行する場合：

```bash
cd /mnt/kiso-qnap5/activities/260915_codex_hackathon/research/vsr/auto_avsr/auto_avsr
bash ../scripts/run_vsr.sh ../outputs/setup/video_only.mp4 ../outputs/my-first-run
```

出力先には**未作成のディレクトリ名**を指定する。`transcript.txt`、`result.json`、確認用の `mouth_crop.mp4` が生成される。
モデルと入力は `cuda:0` に配置し、CUDAを利用できなければエラーで停止する。
顔検出・口領域切り出しはCPU、読唇モデルとbeam searchはGPU。
この環境ではCodexサンドボックス内からGPUへアクセスできず、承認済みのサンドボックス外実行で成功した。

自分の動画も第1引数に指定できる。入力は音声トラックなし・25 fpsの短い英語動画を使う。
音声付き・25 fps以外の入力は拒否する。元動画は保存し、別ファイルへ `ffmpeg -i original.mp4 -map 0:v:0 -vf fps=25 -an video_only.mp4` などで変換する。
本環境にシステム版ffmpegはないため、必要なら `.venv/bin/python -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())'` が示す同梱バイナリを使う。
長動画の分割や複数話者選択は実装していない。

## 環境の再構築

以下は親 `research/vsr/auto_avsr/` で実行する。
uvは既存の `/tmp/usr2-bootstrap/bin/uv`（0.12.10）を使用した。`uv` は現在PATHにない。
`/tmp` のuvが消えた場合は[公式インストール手順](https://docs.astral.sh/uv/getting-started/installation/)で用意する。

```bash
cd /mnt/kiso-qnap5/activities/260915_codex_hackathon/research/vsr/auto_avsr
UV_BIN=/tmp/usr2-bootstrap/bin/uv bash scripts/setup_uv.sh
bash scripts/download.sh
```

`setup_uv.sh` はPython 3.10専用venvに固定済み80パッケージを同期する。
初回は既存USR2環境のPython 3.10.21インタープリターでvenvを作成したが、site-packagesは共有しない。
新規マシンではuvがPython 3.10を取得する。Python本体の保存先は既定 `/tmp/auto-avsr-uv-cache/python` のため、永続化する場合は `UV_PYTHON_INSTALL_DIR` を指定する。
主要依存：PyTorch 2.5.1+cu124、torchvision 0.20.1+cu124、torchaudio 2.5.1+cu124、Lightning 2.5.0.post0、MediaPipe 0.10.21、NumPy 1.26.4、PyAV 13.1.0。
全依存は `requirements-uv.lock`、直接依存は `requirements-uv.in`。

`download.sh` は重み約1.00 GBとサンプルZIP約24.5 MBを取得し、SHA256を照合する。
既存ファイルも照合し、不一致なら停止する。原本から映像トラックをコピーして無音声版を作成する。
全LRS2/LRS3データセットや18 GBのランドマークは今回取得していない。

## READMEとの対応

- [上流README](auto_avsr/README.md)のSetupとModel zooに従い、`vsr_trlrs2lrs3vox2avsp_base.pth` を取得。ASR用の音声モデルとは別。
- [preparation/README.md](auto_avsr/preparation/README.md)に沿って顔検出→平均顔への位置合わせ→96×96口領域切り出しを実施。上流 `VideoTransform(test)` で88×88中心crop、グレースケール、正規化（平均0.421、標準偏差0.165）。
- 単体推論は `tutorials/inference.ipynb` のvideo経路を使用。明示的なCUDA配置、音声トラック検査、計測・保存を補助スクリプトへ追加。beam size 40、CTC weight 0.1は上流既定。
- 検出器は上流対応のMediaPipe。旧 `mp.solutions` APIを使うため0.10.21に固定。
- tutorialのデモ配布URLはHTTPSで404だったため、LipVoicer公開LRS3サンプルへ変更。

モデル出力へLLM補正・翻訳・正解文入力は加えていない。信頼度の確率は提供されないため `null`。
コードはApache 2.0。上流は重みに学習データ由来の条件があり得ると記載する。
重み・サンプルの個別利用条件は未確認の部分があり、ローカル検証用に保存した。再配布はしていない。

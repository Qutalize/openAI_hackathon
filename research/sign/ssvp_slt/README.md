# SSVP-SLT：学習済みSONARによるASL動画→英文

2026-09-12 Git管理更新：既存の上流コード・設定・文書をルートのGitへ集約しました。
この作業ツリーでは上流コードは配置済みで、以下の過去の準備例にある上流への `git clone`・`git checkout`・パッチの再適用は不要です。
動画・重み・生出力は引き続きローカル管理です。上流ディレクトリ全体をGit対象外とする従来の記述は、この方針で置き換えます。
取得元revision、除外資材の準備、復元方法は [Git管理の集約](../../../docs/07-git-consolidation.md) を参照してください。

入力言語はASL（米国手話）、出力言語は英語。利用者による学習・ファインチューニングを行わず、公式の `examples/sonar/run.py` を使用する。
2026-09-12：環境構築と公式サンプル推論に成功し、公式READMEの期待出力と一致した。
自前ASL動画2本も英文を生成したが、両方とも正解と不一致だった。
環境・推論経路の再現は成功、実用的な翻訳精度の確認は未達。実行結果は [検証報告](reports/2026-09-12-sonar-asl.md) を参照。

追加ASL動画07・08の3モデル比較も実施した。出力は `Yes. Very.` / `We are 6.6.` で両方意味不一致、
2本全体WERは100%。CLI全体は148.29秒・181.08秒、GPU全体の観測ピークは最大8.065GiBだった。
CPU顔検出が主な待ち時間。[07・08の精度・速度・GPU計測報告](reports/2026-09-12-pro-07-08-comparison.md)を参照。

## この経路を使う理由

[公式SONAR推論README](https://github.com/facebookresearch/ssvp_slt/blob/7ed332b0db35884a36b73019ca29bf0755537def/examples/sonar/README.md) と
[demo.sh](https://github.com/facebookresearch/ssvp_slt/blob/7ed332b0db35884a36b73019ca29bf0755537def/examples/sonar/demo.sh) に、
動画入力の推論入口、学習済みSignHiera、SONAR ASL encoderの配布URLがある。
SONAR decoderとtokenizerはSONARパッケージの公式asset cardに従い取得する。

SignHiera単体は映像特徴抽出器であり、英文を返す翻訳器ではない。
今回使う一式は著者側でDaily MothのASL映像に調整済み。これは利用者が追加学習するという意味ではない。
公式READMEは未知の話者・分野への汎化が弱い可能性を明記している。

[論文](https://aclanthology.org/2024.acl-long.467/) のHow2Sign評価と、このSONAR公開デモの結果は別に扱う。
[translation/README.md](https://github.com/facebookresearch/ssvp_slt/blob/7ed332b0db35884a36b73019ca29bf0755537def/translation/README.md) の学習・評価経路は別途finetuned T5を要求するため、今回はSONARの完成済み重みを使う。

## 配置

- `upstream/`：公式checkout。revision `7ed332b0db35884a36b73019ca29bf0755537def`。
- `.venv/`：独立したPython 3.10環境。
- `weights/`：SignHiera、SONAR ASL encoder、dlib CNN顔検出器、T5設定、SONAR decoder/tokenizerキャッシュ。
- `outputs/`：動画、ログ、未補正の生成文、入力・重みSHA256等。Git対象外。
- `scripts/`、依存定義、報告：再現用の自作補助。

## 自前動画の推論

作業ディレクトリはプロジェクトルート。環境と重みの準備後、次を実行する。

```bash
research/sign/ssvp_slt/.venv/bin/python \
  research/sign/ssvp_slt/scripts/run_video.py \
  data/sign/01_whats_your_name/original.mp4
```

別動画は最後のパスを変更する。保存先は自動で一意に作り、画面に表示する。
`--output research/sign/ssvp_slt/outputs/my-run` で指定も可能。既存の保存先は拒否する。

- `prediction.txt`：成功時の未補正の生成英文。
- `result.json`：実行成否、英文、入力・重みのハッシュ、revision、実行コマンド、時間。
- `inference.log`：上流の標準出力・標準エラー、重みロード結果。
- `command.txt`：環境変数を含む上流再実行コマンド。
- `environment.txt`：Python・全パッケージ・GPU・dlib情報をJSONで保存。
- `hydra/.hydra/config.yaml`：上流が実際に使った前処理・推論設定。

映像のみをOpenCVで読み、音声と `script.txt` はモデルへ渡さない。動画のアップロードは行わない。
信頼度は上流が返さないため `null`。生成成功と翻訳の意味の正しさは別に評価する。
モデルは `eval()` と `inference_mode()` を使う。optimizerや学習コマンドは呼び出さない。

## 別環境での準備

Linux、Python 3.10、CUDA対応GPU、C++コンパイラ、systemの `libsndfile.so.1` が必要。
このマシンではPython 3.10.21の実行本体のみ既存LiTFiC環境から借りてvenvを作成し、site-packagesを分離した。
他のモデル環境へのパッケージ追加は行わない。

```bash
git clone https://github.com/facebookresearch/ssvp_slt.git research/sign/ssvp_slt/upstream
git -C research/sign/ssvp_slt/upstream checkout 7ed332b0db35884a36b73019ca29bf0755537def
git -C research/sign/ssvp_slt/upstream apply ../patches/sonar-0.2.1-dtype.patch
uv venv --python python3.10 research/sign/ssvp_slt/.venv
uv pip install --python research/sign/ssvp_slt/.venv/bin/python \
  -r research/sign/ssvp_slt/requirements-inference.txt cmake==3.31.6
PATH="$PWD/research/sign/ssvp_slt/.venv/bin:$PATH" CMAKE_BUILD_PARALLEL_LEVEL=4 \
  uv pip install --python research/sign/ssvp_slt/.venv/bin/python dlib==19.24.6
uv pip check --python research/sign/ssvp_slt/.venv/bin/python
python3 research/sign/ssvp_slt/scripts/download_assets.py
```

この環境のuv実行本体は `/tmp/usr2-bootstrap/bin/uv`、キャッシュは `/tmp/ssvp-uv-cache` を使用。
`download_assets.py` は取得済みファイルを保持し、取得元と計算したSHA256を `weights/assets.json` に記録する。
T5は `google/t5-v1_1-large` revision `a98b0fcd0b8137ded40cdf0c0cf0ee884e7c9726` のconfigのみ取得する。
T5の一般重みを追加ダウンロードする必要はなく、学習済みSONAR ASL checkpointをロードする。
SONAR decoder/tokenizerは初回実行時に追加取得される。

公式サンプル：

```bash
research/sign/ssvp_slt/.venv/bin/python \
  research/sign/ssvp_slt/scripts/run_video.py \
  research/sign/ssvp_slt/outputs/public-sample/0043626-2023.1.4.mp4
```

## 上流手順からの調整

- [INSTALL.md](https://github.com/facebookresearch/ssvp_slt/blob/7ed332b0db35884a36b73019ca29bf0755537def/INSTALL.md) の学習用依存一式を導入せず、SONAR推論に必要な依存を抽出した。`PYTHONPATH=upstream/src` で上流をimportする。
- fairseq2n 0.2.1のPyPI wheelはPyTorch 2.2.2を厳密に要求する。torchvision 0.17.2、torchaudio 2.2.2、SONAR 0.2.1、fairseq2 0.2.1へ固定。最新版一括導入は避ける。
- Transformersは現上流指定の範囲内の4.50.3、NumPyは1.26.4へ固定する。
- dlibはCMakeの先行導入が必要。このマシンにはCUDAコンパイラがなく、顔検出はCPUビルド。特徴抽出・翻訳はPyTorch CUDAを使う。
- 親の `CONDA_PREFIX` があるとfairseq2nがsystemのlibsndfileを探さないため、venvの子プロセスではこの変数を除く。
- `TORCH_HOME`、`HF_HOME`、`XDG_CACHE_HOME` をweights配下へ指定する。fairseq2 0.2.1の実際の保存先は `weights/cache/fairseq2/assets/`。
- T5 configの参照先を固定済みローカルディレクトリへ指定する。
- SONAR 0.2.1のpipelineコンストラクタには `dtype` 引数がない。公式loaderでdecoderを指定dtypeにロードし、そのinstanceをpipelineへ渡す [互換patch](patches/sonar-0.2.1-dtype.patch) を適用した。学習・重み変更は行わない。
- [artifacts.sha256](artifacts.sha256) に追加取得したdecoder/tokenizerも含むSHA256、[requirements-inference.lock.txt](requirements-inference.lock.txt) に実際の全依存版を保存した。

## 前処理と制約

上流のdlib CNNによる顔検出（16フレームごと）→顔枠拡張→正方形cropと224×224リサイズ→時間サンプリング。
既定target FPS 25、sampling rate 2、128フレーム窓、feature extraction stride 64、最大batch 2。
128フレームを25fpsで単純に読む設定とは異なり、窓長は元fpsに応じ `2×128/25×元fps` で計算される。
短動画は末尾を複製してpaddingをモデルに渡す。RGBを0〜1へ変換し、mean 0.45、std 0.225で正規化。
顔が見つからない場合等に上流は中央cropを使うことがあり、完走だけで正しい人物cropを保証しない。
長い会話の文分割機能はこのCLIにはなく、まず一文程度の短いASL動画で使用する。
この環境ではフルHDの約4〜5秒の動画でCPU顔検出に約327〜410秒かかった。現在の構成はリアルタイムではない。
上流には `preprocessing.detection_downsample=true` もあるが、今回の結果は既定のfalseで測定している。
顔検出用縮小やCUDA版dlibによる速度・出力の変化は未検証。

主ライセンスは上流README記載のCC-BY-NC 4.0。構成要素はそれぞれの配布条件も参照。

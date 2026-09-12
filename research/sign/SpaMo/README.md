# SpaMo：自前ASL動画の推論検証

2026-09-12 Git管理更新：既存の上流コード・設定・文書をルートのGitへ集約しました。
この作業ツリーでは上流コードは配置済みで、以下の過去の準備例にある上流への `git clone`・`git checkout`・パッチの再適用は不要です。
動画・重み・生出力は引き続きローカル管理です。上流ディレクトリ全体をGit対象外とする従来の記述は、この方針で置き換えます。
取得元revision、除外資材の準備、復元方法は [Git管理の集約](../../../docs/07-git-consolidation.md) を参照してください。

調査日：2026-09-12。入力はASL（米国手話、ユーザー確認済み）、希望出力は英文。
学習・ファインチューニングは行わない。実行結果は [検証報告](reports/2026-09-12-local-asl.md) を参照。

[追加動画07・08の検証と3モデル比較用計測](reports/2026-09-12-pro-07-08-comparison.md)も完了。
How2Sign用の第三者版で2本とも英語生成に成功したが、07は数字列、08は誤った名前と原稿にない謝辞を生成した。
3モデル共通の採点ではBLEU-4 2.23、ROUGE-L 0.00、WER 185.71%、完全一致0/2本。
外部CLI全体は46.25秒／38.22秒、nvidia-smiによるdevice peakは6.435／6.577 GiB。
同じ原動画・GPU直列実行による比較用の値であり、常駐モデルの生成時間とは区別する。

**追加調査で第三者提供のHow2Sign用SpaMo checkpointを発見。**
[SpaMo-Sign-VLA](https://github.com/HGardner1108/SpaMo-Sign-VLA) がASL→英語用の重み・設定・推論コードを公開している。
詳細は [追加調査と検証](reports/2026-09-12-how2sign-weight-search.md) を参照。
重みの取得と自前動画2本でのGPU推論まで完了。英語は生成されたが、どちらも正解内容に合わず、正確なASL翻訳は未達。
[自前動画の採点結果](reports/2026-09-12-local-asl-accuracy.md)：完全一致0/2本、BLEU-4 0.43、ROUGE-L F1×100 6.82。
最初に試した公式Dropbox重みは英語promptでも天気に関するドイツ語を生成した。以下の初回調査の記述は公式公開版についてのもの。

## 調査上の判断

SpaMoは動画の空間特徴（CLIP ViT-L/14＋S²）と動き特徴（VideoMAE-L）を、学習済みSign AdapterとLoRA付きFlan-T5-XLへ渡す。
一般のCLIP・VideoMAE・Flan-T5だけを取得しても、手話と英文の対応を学習した部分が欠ける。
論文の「without visual fine-tuning」は視覚エンコーダを固定する意味であり、翻訳器全体が未学習で使えるという意味ではない。
既にASLで学習されたSpaMo一式があれば、自分で追加学習せずに推論する構成は可能。

ただし公開リポジトリの `configs/finetune.yaml`、`dataset/p14t.py`、付属注釈はPHOENIX14T（DGS／ドイツ手話→ドイツ語）用。
How2Sign（ASL→英語）は論文の評価対象だが、今回確認した公式コード・README・Release・IssueにはHow2Sign専用の推論設定・重みへの案内を確認できなかった。
READMEの単一 `spamo.ckpt` は学習言語を明記していないため、ASL対応済みとして扱えない。
`lang='English'` は出力指示であって、DGSとASLの入力言語差を解消する方法ではない。

## 配置

- `SpaMo/`：ユーザー指定の既存上流checkoutを維持。revision `aee7f8b6ea8201b710690adcce6f46260dd11bba`。変更しない。
- `.venv/`：SpaMo専用環境。既存モデルの環境へ依存を追加しない。
- `weights/spamo.ckpt`：公式Dropbox重み。
- `weights/{clip,videomae,t5}/`：視覚モデル、T5設定・tokenizer。T5本体はSpaMo checkpointから厳格ロードする。
- `weights/assets.json`：各Hugging Face revision・取得ファイルSHA256。
- `outputs/`：原動画のハッシュ、特徴、生成文、処理時間、ログ。Git対象外。
- `scripts/`：自作補助。UI/APIには依存しない。

## 環境構築

リポジトリルートを作業ディレクトリとする。Python 3.9.25で構築した。
ここでは `uv` がPATHにあり、Python 3.9が使用可能な例を示す。
このマシンではuvは `/tmp/usr2-bootstrap/bin/uv`、Pythonは `/home/kosaki/anaconda3/envs/Uni-Sign/bin/python` を環境作成時のインタープリタとして使った。
仮想環境は独立しており、Uni-Signのsite-packagesは継承しない。

```bash
uv venv --python python3.9 research/sign/SpaMo/.venv
uv pip install --python research/sign/SpaMo/.venv/bin/python \
  -r research/sign/SpaMo/requirements-inference.lock.txt
uv pip check --python research/sign/SpaMo/.venv/bin/python
```

主な条件はPyTorch 2.0.1、torchvision 0.15.2、Transformers 4.32.0、PEFT 0.7.1、Lightning 1.9.5、NumPy 1.26.4。
元requirementsは学習用パッケージも含み、動画デコード用PyAV、torchvision、SentencePieceなどが明示されていない。
`requirements-inference.txt` は単体推論に必要なものを分離したもの。
`requirements-inference.lock.txt` は実際に導入したパッケージの固定一覧。追加調査のSign-VLA用前処理にOpenCVを追加した。
Lightningが使う `pkg_resources` のためsetuptoolsは69.5.1へ固定した。
GPUはRTX A6000 48GB、ドライバ590.48.01。ドライバのCUDA表示とPyTorch内蔵CUDAランタイムの版は別物。

重み取得（既に取得済みのこの作業環境では再ダウンロード不要）：

```bash
mkdir -p research/sign/SpaMo/weights
curl -fL --retry 2 \
  'https://www.dropbox.com/scl/fi/c9khflgxgl96lx919p6oq/spamo.ckpt?rlkey=gp3zmk6jwg9cnf3e2hpw268ih&dl=1' \
  -o research/sign/SpaMo/weights/spamo.ckpt
research/sign/SpaMo/.venv/bin/python research/sign/SpaMo/scripts/download_assets.py
```

`download_assets.py` は `model-revisions.json` の検証済みrevisionを使い、取得ファイルのSHA256とともに `weights/assets.json` に保存する。
既存 `weights/assets.json` がある場合はそのrevisionを優先する。`artifacts.sha256` には今回取得した重み等のハッシュを記録した。
公式チェックポイントの対象手話言語が未確認という制約は、ダウンロードが成功しても残る。

## 単体推論

```bash
research/sign/SpaMo/.venv/bin/python research/sign/SpaMo/scripts/run_video.py \
  data/sign/01_whats_your_name/original.mp4 \
  --output research/sign/SpaMo/outputs/my-asl-run \
  --languages English
```

出力先は新規ディレクトリを指定する。`result.json` に未補正の生成文字列、requested output language、checkpoint情報、時間、ピークGPUメモリを保存する。
信頼度は上流で提供されないため `null`。生成成功と意味の正しさは別に扱う。
既定はseed=0、上流同様beam=5、top_p=0.9、do_sample=True、max_length=64。
サンプリングとGPU計算のため、異なる環境での完全一致までは保証しない。

処理内容：

1. PyAVで映像ストリームのみRGBデコード。音声・`script.txt` はモデルへ渡さない。
2. 元FPSの全フレームをCLIPの公式processorで処理。S²のscaleは1と2、各フレーム2048次元。
3. VideoMAEは16フレーム窓・stride=8。16未満なら末尾を複製、途中から最後の不完全窓は上流と同様に除く。各窓1024次元で、上流実装と同じ最初のトークンを使う。
4. 上流 `prepare_visual_inputs` とfusion層、T5のprompt embedding、`generate` を使用。
5. T5・LoRA・projector・temporal encoderをcheckpointから `strict=True` でロードし、`eval()`・`inference_mode()` で実行。optimizerやTrainer.fitを呼ばない。

上流の `get_inputs` は1件でも `derangement` を呼び、2件以上というassertに失敗する。
さらに `en_text/fr_text/es_text/text` を要求する。自前動画だけの推論ではこの経路を使わず、直接特徴と出力言語promptを組み立てる。
`use_in_context=False` とし、正解由来の翻訳例を使用しない。論文のICL付き評価を厳密再現したものではない。
上流 `read_video` は `av` のimportがなく失敗するので、自作のPyAVデコーダで読み込む。
512フレームを超える動画はランダムcropせず停止する。長い動画は手話の意味が保たれる区間に分割して使う。

## ASL翻訳として使うために残る条件

必要なのはHow2Sign向けの学習済みSpaMo checkpointと、その重みに対応する設定・前処理・推論prompt。
公式の単一checkpointがそれに該当するかは未確認。出力言語だけの変更や正解文のprompt挿入を代替手段にしない。
適切なcheckpointを取得できれば、その構成に合わせて `load_model` のモデル寸法・LoRA設定を照合し、同じ動画を再実行する。
この作業では新規学習も代替モデルへの置換も行っていない。

### 追加調査で見つかった第三者版

配布元：[HGardner1108/SpaMo-Sign-VLA](https://github.com/HGardner1108/SpaMo-Sign-VLA)。
重み：[Spamo_How2sign.ckpt（Google Drive）](https://drive.google.com/file/d/1huqKMCsJbc0C2zaUiFffqNaYGHKdksJF/view)。
上流の公式How2Signモデルであるとは確認していない。配布者がHow2Signで学習したASL→英語モデルと説明している。

このマシンでは対応コードを `upstream/sign-vla/`、重みを `weights/spamo_how2sign_sign_vla.ckpt` に配置する。
コードrevisionは `d34bc0b62927a5b1b1b3f4fefcc0828c3f0b9983`。
再取得時は上記リポジトリを同じ場所へcloneし、そのrevisionへcheckoutする。

```bash
research/sign/SpaMo/.venv/bin/python research/sign/SpaMo/scripts/run_video.py \
  data/sign/01_whats_your_name/original.mp4 \
  --variant sign-vla \
  --output research/sign/SpaMo/outputs/sign-vla-retry \
  --languages English
```

`--variant sign-vla` は配布者の動画推論コードに合わせ、210:260で中央crop→210×260へOpenCV resizeし、
空間8トークンと動き1トークンを交互に結合する派生モデルを使用する。生成はbeam=5、samplingなし。
特徴抽出器のforward・S²・temporal encoder等は確認した両コードで同等の処理を使う。
重みロードは欠落を許容する配布者の `strict=False` ではなく、全項目の `strict=True` としている。

## 一次資料

- [公式コード・重み案内](https://github.com/eddie-euijun-hwang/SpaMo)
- [論文、特に§3とAppendix A/B](https://aclanthology.org/2025.naacl-long.197/)
- [固定revisionの設定](https://github.com/eddie-euijun-hwang/SpaMo/blob/aee7f8b6ea8201b710690adcce6f46260dd11bba/configs/finetune.yaml)
- [How2Sign公式：ASLと英文のデータセット](https://how2sign.github.io/)
- [How2Signの再現に関するIssue #17](https://github.com/eddie-euijun-hwang/SpaMo/issues/17)
- [How2Sign前処理に関するIssue #2](https://github.com/eddie-euijun-hwang/SpaMo/issues/2)
- [ICLの評価時の扱いに関するIssue #12](https://github.com/eddie-euijun-hwang/SpaMo/issues/12)

Issueの第三者による再現失敗は、この環境での実測とは区別する。公開重みのASL非対応をそれだけで断定しない。

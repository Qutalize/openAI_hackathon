# LiTFiC：重みの入手と自前動画から英文を生成するための調査

調査日：2026-09-12。コード読解・一次資料調査・HTTPヘッダー確認のみ実施。重み本体のダウンロード、環境構築、推論は未実施。

対象checkout：`../LiTFiC/`、revision `f8cb85e3c9eed29a0a6a222e80b483efa0353d10`。既存checkoutは変更していない。

## 結論

- 公式の `bobsl_all.ckpt` は配布中。HTTP HEADで200 OK、18,632,777,067 bytes（約18.6 GB / 17.35 GiB）を確認した。全体取得・内容検査・SHA256照合は未実施。
- 配布されているのはBOBSL用、つまり英国手話（BSL）から英語へのモデル。論文にはHow2Sign（米国手話、ASL）の実験もあるが、今回確認した公式配布経路ではHow2Sign用の翻訳checkpoint・対応設定は見つからなかった。BSL用重みをASLや日本手話対応とは扱えない。
- 公開コードは抽出済み動画特徴（LMDB）を入力する。任意のMP4を渡す完成済み推論CLIは見当たらない。自前動画には、学習時と整合する特徴抽出器と、単一動画用の推論ラッパーを別途用意する必要がある。

出典：[公式README](https://github.com/art-jang/LiTFiC)、[プロジェクト](https://www.robots.ox.ac.uk/~vgg/research/litfic/)、[論文](https://arxiv.org/html/2501.09754v2)。

## 重みのダウンロード

以下は実行用の案内であり、今回ダウンロードはしていない。現在の配置を前提とし、重みをcheckoutの外の `weights/` に置く。

```bash
cd /mnt/kiso-qnap5/activities/260915_codex_hackathon/research/sign/LiTFic
mkdir -p weights
curl -fL --retry 3 -C - \
  https://mm.kaist.ac.kr/share/jyj/LiTFiC/bobsl_all.ckpt \
  -o weights/bobsl_all.ckpt
sha256sum weights/bobsl_all.ckpt > weights/bobsl_all.ckpt.sha256
```

SHA256は取得物の再現記録用。公式の期待ハッシュは確認していないので、これだけで公式配布物との照合が完了したとはいえない。HTTP応答は `Accept-Ranges: bytes` を返しており、上のコマンドは再開ダウンロードを指定している。

さらに、上流の初期化処理は `AutoTokenizer.from_pretrained` と `AutoModelForCausalLM.from_pretrained` を呼ぶため、**Meta-Llama-3-8BのTransformers形式のモデル・設定・tokenizerも必要**。checkpoint本体に何が含まれるかは未検査だが、公開コードをそのまま使う場合はこの初期化を省けない。

[Meta公式モデルページ](https://huggingface.co/meta-llama/Meta-Llama-3-8B)でアクセス申請・条件への同意を行い、権限のあるアカウントで取得する。`Meta-Llama-3-8B-Instruct` やLlama 3.1等に置き換えない。アクセス権と `huggingface_hub` 導入済み環境を前提とした取得例：

```python
from huggingface_hub import login, snapshot_download

login()  # トークンは対話入力。ソースへ書き込まない
snapshot_download(
    repo_id="meta-llama/Meta-Llama-3-8B",
    local_dir="weights/Meta-Llama-3-8B",
    allow_patterns=["*.json", "*.safetensors", "tokenizer.model"],
)
```

作業ディレクトリは上と同じ `research/sign/LiTFic/`。取得時にはHF revisionも記録する。Llama用にも追加のディスク容量が必要。

## 公開評価コードを動かす場合

上流が案内する主要環境はPython 3.10、PyTorch 2.3.1、torchvision 0.18.1、CUDA 12.1。requirementsにはTransformers 4.45.2、PEFT 0.12.0、Lightning 2.3.0、flash-attn 2.7.2.post1等がある。インストール互換性は未検証。

```bash
cd /mnt/kiso-qnap5/activities/260915_codex_hackathon/research/sign/LiTFic/LiTFiC
conda create -n litfic python=3.10
conda activate litfic
pip install torch==2.3.1 torchvision==0.18.1 --index-url https://download.pytorch.org/whl/cu121
pip install -r requirements.txt
conda install bioconda::java-jdk
```

`src/eval.py` はBOBSLのテストセット評価用。重みとLlamaだけでは足りず、`configs/paths/default.yaml` にある以下のパスも実体へ合わせる必要がある。

- split、動画メタデータ、字幕、手動整列字幕、8,697語の語彙、同義語。
- SWIN FEATURES V2のLMDBと、そのpseudo-label LMDB。
- BLIP2背景caption、テスト・検証エピソード開始index、過去captionのファイル。
- BLEURTモデル。これは英文生成用ではなく正解文との比較評価用。

[データ準備README](https://github.com/art-jang/LiTFiC/tree/main/configs/paths)、[CSLR2注釈](https://gulvarol.github.io/cslr2/data.html)、[BOBSL配布ページ](https://www.robots.ox.ac.uk/~vgg/data/bobsl/)参照。BOBSLの該当特徴データにはアクセス申請が必要。LMDB全体は約262 GBなので、単一自前動画用推論を作る場合はこの全体取得を必須条件にしない。

追加資料の[配布ページ](https://mm.kaist.ac.kr/share/jyj/LiTFiC/download.html)はcurlで取得できた。掲載ファイルは `test_start_indices.json`、`val_start_indices.json`、`prev_captions.json`。READMEの `train_cap_path` の表は `val_start_indices.json` と書かれている一方、設定は `prev_gt_captions.json` であり、表記が一致していない。実ファイル内容を確認してパスを指定する必要がある。

全データパスを設定した後の評価起動例（未実行）：

```bash
python src/eval.py \
  experiment=vid+pg+prev+bg \
  'trainer.devices=[0]' \
  logger=csv \
  task_name=litfic-eval \
  ckpt_path=../weights/bobsl_all.ckpt \
  paths.llm_root=../weights/Meta-Llama-3-8B
```

1 GPU指定は起動構成の例であり、必要VRAMを満たすとの確認ではない。推論VRAM・速度は未測定。`src/llm_eval.py` の外部APIは追加採点用で、手話から英文を生成するためには不要。

## 自前動画から英文にする経路

```text
BSL動画を文単位に切り出す
  → 手話者を切り抜き、対応するVideo-Swinの前処理を適用
  → BOBSL用ISLR Video-Swinで特徴系列 [T, 768] を抽出
  → 同じISLR分類器からpseudo-glossを生成
  → 動画特徴 + pseudo-gloss + 前文の予測 + 背景説明
  → LiTFiCの学習済みMLP + Llama 3 / LoRA
  → 英文
```

論文3.2では、8,697手話クラスで学習したVideo-Swinを使用する。25 fps、連続16フレームごとの窓、BOBSLではstride 2で抽出し、最終分類層の直前を時空間平均した768次元ベクトルを得る。空間crop・resize・正規化・端のpaddingも使用する抽出器に合わせる。単に任意の768次元特徴を作っても互換ではない。

**残っている主要課題は、SWIN FEATURES V2を生成したものと一致するISLR重み・設定・抽出処理の確保。** [CSLR2公式](https://github.com/gulvarol/cslr2)のREADMEでは主に抽出済みLMDBの利用が案内されており、今回の調査でこの組の直接取得手順を特定できなかった。

関連する[Transpeller公式](https://github.com/prajwalkr/transpeller)には `video-swin-s.pth` とRGB動画から特徴を作る例がある。ただし旧世代のSwin-Sで、LiTFiCが設定するV2/Tiny系列との一致は未確認。代用品として無条件に接続せず、LiTFiC/CSLR2の作者に **BOBSL Swin V2 ISLR checkpoint、分類head、8697語のクラス順、動画前処理と特徴抽出コード** を確認するのが確実。問い合わせの送信はしていない。

単一動画用ラッパーは、BOBSLの巨大なデータローダーを通さず次の処理を実装する。

1. `configs/experiment/vid+pg+prev+bg.yaml` 相当の設定で `VggSLTNet` を構築し、checkpointをロードする。単体netにロードする場合の `net.` prefix変換、必要キーと形状の一致は取得後に検査する。安易な `strict=False` でロード漏れを無視しない。
2. `features=[1,T,768]` と `attn_masks=[1,T]` を作り、`mm_projector` で `[1,T,4096]` に変換する。
3. `LanguageDecoder._predict()` に動画埋め込みとテキスト条件を渡す。`eval()` と `torch.inference_mode()` を使う。
4. 返るtoken ID列をtokenizerの `decode(..., skip_special_tokens=True)` で英文にする。現在の上流生成コードは `max_new_tokens=50`。

対応箇所：`src/models/components/vgg_slt.py`、`src/models/components/vgg_slt_modules/language_decoder.py`、`src/models/components/vgg_slt_modules/mm_projector.py`。

実装時の入力条件：

- 指示文は `src/data/components/subtitles.py` の既存英語promptに合わせる。
- PGは認識器による単語ラベル候補で、英訳の正解文ではない。語彙対応、同義語集約、連続重複圧縮は `src/data/components/sentence.py` に合わせる。
- 最初の短動画では前文の予測は空。連続文では直前の生成文を渡し、別動画へ移るとリセットする。
- 背景説明は論文ではBLIP2による番組映像の説明。自前動画が無地背景なら空で試せるが、学習時の条件とは異なる。
- `_process_predict` は空PGや空背景を `Not available` と扱う分岐を持つ。その形で疎通を試すことは可能と読めるが、翻訳品質は未検証。空入力を `None` にするだけではなく関数が期待するリスト形状を保つ。
- 正解の英文を入力する必要はない。生成専用 `_predict` 経路では `subtitles` の本文を生成promptへ加えない。上流の通常forwardは損失計算も行うため、単体推論では生成経路を分ける。
- 全条件用checkpointからPG/BGを省いた結果を、別途学習した `experiment=vid` のモデルの再現とは呼ばない。

## 次に進める順序

1. 自前動画がBSLであることを確認。ASLならHow2Sign用の翻訳・視覚encoder重みと設定の確保が先。
2. BOBSL用翻訳checkpointと、権限取得後のLlamaをダウンロードし、revision・SHA256・依存を記録。
3. 対応するVideo-Swin V2の取得元を確定。取得済みBOBSL特徴がある場合は、先にその1文で翻訳部分を検証できる。
4. 正しい視覚特徴が用意できてから単一動画用ラッパーを作り、短いBSL動画1本で実出力を確認。

現時点では「翻訳重みの配布は確認済み」「自前MP4から英文の一貫推論は未実施」である。

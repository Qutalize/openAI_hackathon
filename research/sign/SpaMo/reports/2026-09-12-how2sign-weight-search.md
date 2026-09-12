# How2Sign用SpaMo重みの追加探索

2026-09-12。ユーザーの追加依頼に基づき、公式配布先に加えて公開fork・Hugging Face・関連プロジェクトを探索した。

## 発見したもの

**第三者提供のHow2Sign用SpaMo checkpointが見つかった。初回調査ではこの配布先を見落としていた。**

| 項目 | 内容 |
|---|---|
| 配布者のリポジトリ | [HGardner1108/SpaMo-Sign-VLA](https://github.com/HGardner1108/SpaMo-Sign-VLA) |
| 重み | [Spamo_How2sign.ckpt](https://drive.google.com/file/d/1huqKMCsJbc0C2zaUiFffqNaYGHKdksJF/view) |
| サイズ | 5,925,402,030 bytes（約5.93GB） |
| コードrevision | `d34bc0b62927a5b1b1b3f4fefcc0828c3f0b9983` |
| 対応設定 | [configs/finetune_how2sign.yaml](https://github.com/HGardner1108/SpaMo-Sign-VLA/blob/d34bc0b62927a5b1b1b3f4fefcc0828c3f0b9983/configs/finetune_how2sign.yaml) |
| 動画推論コード | [Translation_Pipeline/translate_video.py](https://github.com/HGardner1108/SpaMo-Sign-VLA/blob/d34bc0b62927a5b1b1b3f4fefcc0828c3f0b9983/Translation_Pipeline/translate_video.py) |
| ローカル保存先 | `weights/spamo_how2sign_sign_vla.ckpt`、`upstream/sign-vla/` |

重み全体の取得完了。SHA256：`140d412d232407cfc3409ba5faf8bb96ede276aadf0223b156c7e3bd6ec37ee3`。
原著版の重みと区別して [artifacts.sha256](../artifacts.sha256) に追記した。

READMEの「Download the SpaMo checkpoint」はASL→英語用にHow2Signで学習した重みと明記している。
Google Driveのファイル名・取得応答・サイズを確認できた。
冒頭のpickle opcode検査でepoch=130、global_step=505122、
保存先 `logs/2026-03-27T23-05-35_spamo_how2sign/checkpoints` を確認。
初回の公式Dropbox重み（epoch=95、step=42624）とは別のcheckpoint。
SpaMo原著者の公式How2Signモデルか、論文の数値を再現する重みかまでは確認できていない。

## 既存の公式版との差

原著版は空間系列の後に動き系列をまとめて結合する。この派生版は空間8トークン→動き1トークンを繰り返す。
モデル構造のtensor寸法が一致しても、結合順序が違うと同じ推論にはならない。
公開動画CLIは中央を210:260の比率でcropして210×260へresizeする。
生成もsamplingからbeam search（beam=5、do_sample=False、length_penalty=1.0）へ変更されている。

このため、既存 `run_video.py` に `--variant sign-vla` を追加した。
派生版の `FlanT5SLT.prepare_visual_inputs` を使用し、公開動画CLIに合わせたcrop・resize・生成条件で実行する。
共通のtemporal encoder・projector・基本Lightningクラス・S²は元版とファイル内容が一致した。
視覚readerのforwardも同じであり、元版の特徴抽出クラスを使用する。
動画読込はPyAV、resizeは公開CLI同様OpenCV。追加した依存はopencv-python-headless 4.8.1.78。

配布者の推論CLIは `strict=False` で一部重みを分けてロードする。
こちらではT5本体・LoRA・adapter一式を `strict=True` で読み込み、欠落した重みを見逃さない構成にした。
配布者の現行推論コードの条件を用いたが、checkpoint作成時の完全な設定・コードrevisionとの対応まで独立検証できたわけではない。
正解原稿を読み込まず、ICLを無効化する。学習・ファインチューニングは実施しない。

## 調べた範囲と他候補

- 公式リポジトリのbranch・tag、初回取得したRelease・Issue。
- GitHub APIが返した公開fork全16件のdefault branchの再帰ファイル一覧。全件 `truncated=false`。
- How2Sign関連ファイルがあるfork3件のREADMEと設定。
- Hugging Faceの `how2sign` 検索92件、前回の `spamo` 検索。
- SignNet-1M、VTaMo、PJM版など関連する配布元。

| 候補 | 確認結果 |
|---|---|
| [Yahia-Ibrahim/SpaMo_HOW2SIGN](https://github.com/Yahia-Ibrahim/SpaMo_HOW2SIGN) | dataset/how2sign.pyとtest注釈はあるが、READMEの重みリンクは元と同じDropbox。独立したHow2Sign重みは見つからず。Releaseも空 |
| [junghyun-dia/SpaMo](https://github.com/junghyun-dia/SpaMo) | How2Sign設定はあるが、READMEの重みリンクは元と同じDropbox |
| [SpaMo-PJM関連モデル](https://huggingface.co/croco-corp/pjm-models) | ポーランド手話向け。ASL→英語用SpaMoの代わりにはならない |
| [SignNet-1M](https://github.com/openhe-hub/SignNet-1M) | SpaMo/How2Sign実験への言及はあるが、公開READMEでは学習済み重みを収録しないと説明 |
| [VTaMo](https://github.com/junyi2005/vtamo) | SpaMo派生の学習コードとHow2Sign設定。既成のHow2Sign用SpaMo重みとは別 |
| [Uni-Sign公式](https://huggingface.co/ZechengLi19/Uni-Sign/blob/main/how2sign_pose_only_slt.pth) | How2Sign用pose-only SLT重みの実ファイルあり。ただしSpaMoへロードする重みではない |

Uni-Signのファイルは1,186,925,007 bytes、HF revision `eab251b7fe7e8521afc0e67be98add670ea40a0d`。
配布メタデータのSHA256は `1bfd5f3312f04e4736f0a52f4ef9535916e6de9676a2a0d00c708748683fb00d`。
共有ワークスペースの `research/sign/uni-sign/README.md` には既にHow2Sign版の検証が記録されているため、新規未検証候補としては扱わない。

探索時の取得JSON・README・配布ページ・ヘッダは `outputs/how2sign-search-20260912/` に保存。

## 自前動画での追加検証

次のコマンドで学習なしのGPU推論を実施する。作業ディレクトリはプロジェクトルート。

```bash
research/sign/SpaMo/.venv/bin/python -u research/sign/SpaMo/scripts/run_video.py \
  data/sign/01_whats_your_name/original.mp4 \
  --variant sign-vla \
  --output research/sign/SpaMo/outputs/20260912-sign-vla-asl-01 \
  --languages English
```

実測で全871項目のstrictロードに成功した。epoch=130、step=505122もtensorロード後に再確認。
1本目の出力は `one, two, three, ...` の繰り返しで、英語にはなったが正しい翻訳ではない。
全文は [result.json](../outputs/20260912-sign-vla-asl-01/result.json) に保存。
信頼度は提供されないためnull。論文のHow2Signベンチマーク値を再現したとは扱わない。

初回のドイツ語出力からは変化したが、自前動画を正確に翻訳する目的は未達。
今回得られた成果は、実体のあるASL用重みの発見・取得・ロードと、提供元の現行推論条件での動作確認。


両動画の実行を完了し、終了コード0・全871項目のstrictロード・特徴の有限値を確認。

| 入力 | 特徴抽出（秒） | モデルロード（秒） | 生成（秒） | 全体（秒） | GPU allocated peak（GiB） |
|---|---:|---:|---:|---:|---:|
| 自前動画1 | 43.67 | 8.04 | 1.21 | 67.33 | 5.65 |
| 自前動画2 | 29.31 | 7.23 | 0.98 | 47.91 | 5.61 |

動画2はボールや守備者を見続けるという内容の英文となり、挨拶の原稿とは一致しなかった。
[動画2の生出力](../outputs/20260912-sign-vla-asl-02/result.json) も保存した。
全体時間はプロセス内計測で、importと初期CUDA準備を除き、重みハッシュ計算を含む。warm latencyや全test精度の測定ではない。

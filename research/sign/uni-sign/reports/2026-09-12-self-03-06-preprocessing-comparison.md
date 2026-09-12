# 03〜06：人物crop・縮小・余白調整の比較

追加4本について、原動画、画素同一の再保存対照、人物crop、crop＋縮小、crop＋余白調整＋縮小の5条件で再推論した。**20/20件の英文生成に成功したが、石けん・水を求める意味に合う翻訳は得られなかった。**

余白調整＋縮小でBLEU-4は1.14→2.14、ROUGE-Lは0→16.03、参考WERは383.33→366.67%となった。05では`I want`という希望表明が出たが、対象は水ではなく長さだった。語句の一致は増えたものの、正訳の獲得・安定した精度改善とは扱わない。

## 1. 前処理と入力保持

入力は03/04の`I want soap.`、05/06の`I want water.`。ASL前提を継続し、各`script.txt`を採点参照とした。実演の個々の指形は独立に意味確認したものではない。正解ラベルや予測は前処理条件の決定に使っていない。

| 条件ID | 処理 |
|---|---|
| original | 未加工原動画を今回の実行系で再推論 |
| reencode | 原動画のデコード画素を完全に保持してFFV1 AVIへ再保存 |
| crop | 全フレームの上半身・顔・手の高信頼点を囲む固定crop |
| crop_resize | crop後に高さ572へ縮小、幅は縦横比を保つ意図で偶数丸め |
| crop_pad_resize | crop後、参照縦横比に近づく左右余白を付けて縮小 |

cropは全フレームのscore>0.3のbody `[0,3..10]`、顔`23..90`、手`91..132`のx包絡に両側5%の余白を付けた。上流モデルが直接選択するのはこのうち69点だが、crop決定には顔全点も含めた。全高さ720を保持し、時間trim・フレーム追加/削除・鏡像反転・回転は行っていない。

| ID | crop `(x,y,w,h)` | crop＋縮小 | 左右追加余白px | 余白後canvas | 余白＋縮小 |
|---|---|---:|---:|---:|---:|
| 03 | 310,0,534,720 | 424×572 | 7 / 7 | 548×720 | 436×572 |
| 04 | 508,0,288,720 | 228×572 | 130 / 130 | 548×720 | 436×572 |
| 05 | 328,0,538,720 | 428×572 | 5 / 5 | 548×720 | 436×572 |
| 06 | 514,0,274,720 | 218×572 | 137 / 137 | 548×720 | 436×572 |

参照は既存How2Sign test 12本の動画寸法中央値（W/H=0.760392、高さ572）。全学習データの分布や必須入力仕様ではない。今回のcropはすべてこの縦横比より細いため、従来の下余白では0pxとなって縮小のみと重複する。そのため今回は左右対称の灰色BGR=(114,114,114)余白で調整した。欠落した身体・手の復元ではない。

04/06は前回の「黒帯除去のみ・幅420」と異なり、人物周辺へさらに絞ったcrop。高信頼対象点の横方向の新規切断は0で、各5代表フレームの目視でも新しい手・顔の明白な切断は見られなかった。未検出領域まで見切れがないことの保証ではない。

16派生動画を全フレーム再デコードして、予定した画像変換と完全一致（最大画素差0）を確認した。original/reencodeも全画素一致。03/04/05/06はそれぞれ127/103/89/109フレーム、30fpsで、全条件256未満のため推論でも間引きなし。条件は生成前に`planned_manifest.json`へ固定した。

## 2. 数値と解釈

各条件4本をまとめた値。20実行は4入力への5条件であり、独立した20サンプルの精度ではない。

| 条件 | BLEU-4 ↑ | ROUGE-L ↑ | WER % ↓ | 完全一致 |
|---|---:|---:|---:|---:|
| 原動画・今回再実行 | 1.14 | 0.00 | 383.33 | 0/4 |
| 再保存対照 | 1.14 | 0.00 | 383.33 | 0/4 |
| crop | 1.09 | 8.75 | 433.33 | 0/4 |
| crop＋縮小 | 1.26 | 6.70 | 366.67 | 0/4 |
| crop＋余白調整＋縮小 | 2.14 | 16.03 | 366.67 | 0/4 |

上流corpus BLEU（13a・case mixed・exponential smoothing）、ROUGE-L F平均×100、既存補助WERを使用。BLEU/ROUGEは正解率ではない。WERは小文字化・句読点除去・語中apostrophe保持の最小語編集数÷GT語数×100で、GT計12語より長い無関係な出力により100%を超える。今回のWER減少は46編集→44編集の2編集分。

全20文に`soap`・`water`はなかった。05の余白調整条件の`I want it to be a little bit longer.`は希望表明の形まで一致したが内容が異なる。06の`thirsty`は水との意味的関連があるものの、第三者の発言や別概念を含み、`I want water.`を伝える文にはなっていない。

今回は原動画と再保存対照が4本ともtoken列まで一致した。一方、05/06の原動画の文は過去実行と異なっている。今回の対照一致を、姿勢再抽出から生成までの一般的な再現性の証明とはしない。各処理の反復分散は未測定で、最も高い指標の条件を最良の翻訳方法として採用する根拠は不足する。

## 3. 全予測と動画リンク

「入力動画」は実際に推論へ渡した動画、「骨格」はその推論で保存したposeを各入力と同じ解像度で重ねた閲覧用MP4。骨格表示のための再推定・再推論はしていない。拡大欄は付けず、手指の元画素との対応を確認できる。MP4はmp4v、音声なし、灰点はモデル未使用点、赤×は低信頼mask点を表す。

### 03_i_want_soap_horizontal

GT：`I want soap.`

| 条件 | 未補正の予測英文 | 入力動画 | 骨格 |
|---|---|---|---|
| 原動画 | I'm going to say I'm going to rinse it down a little bit. | [動画](../../../../data/sign/03_i_want_soap_horizontal/original.mp4) | [骨格](../Uni-Sign/outputs/20260912-self-03-06-preprocessed-pose-overlays-r1/03_i_want_soap_horizontal/original/pose_overlay.mp4) |
| 再保存対照 | I'm going to say I'm going to rinse it down a little bit. | [動画](../Uni-Sign/outputs/20260912-self-03-06-preprocessed-r1/03_i_want_soap_horizontal/reencode.avi) | [骨格](../Uni-Sign/outputs/20260912-self-03-06-preprocessed-pose-overlays-r1/03_i_want_soap_horizontal/reencode/pose_overlay.mp4) |
| crop | You're going to want to make sure that you're getting the right moisture and the right moisture. | [動画](../Uni-Sign/outputs/20260912-self-03-06-preprocessed-r1/03_i_want_soap_horizontal/crop.avi) | [骨格](../Uni-Sign/outputs/20260912-self-03-06-preprocessed-pose-overlays-r1/03_i_want_soap_horizontal/crop/pose_overlay.mp4) |
| crop＋縮小 | You're going to want to make sure that it's nice and centered. | [動画](../Uni-Sign/outputs/20260912-self-03-06-preprocessed-r1/03_i_want_soap_horizontal/crop_resize.avi) | [骨格](../Uni-Sign/outputs/20260912-self-03-06-preprocessed-pose-overlays-r1/03_i_want_soap_horizontal/crop_resize/pose_overlay.mp4) |
| crop＋余白＋縮小 | You're going to want to say you're going to want to take it to the center. | [動画](../Uni-Sign/outputs/20260912-self-03-06-preprocessed-r1/03_i_want_soap_horizontal/crop_pad_resize.avi) | [骨格](../Uni-Sign/outputs/20260912-self-03-06-preprocessed-pose-overlays-r1/03_i_want_soap_horizontal/crop_pad_resize/pose_overlay.mp4) |

### 04_i_want_soap_vertical

GT：`I want soap.`

| 条件 | 未補正の予測英文 | 入力動画 | 骨格 |
|---|---|---|---|
| 原動画 | I'm going to take my tissue paper and I'm going to take my tissue paper. | [動画](../../../../data/sign/04_i_want_soap_vertical/original.mp4) | [骨格](../Uni-Sign/outputs/20260912-self-03-06-preprocessed-pose-overlays-r1/04_i_want_soap_vertical/original/pose_overlay.mp4) |
| 再保存対照 | I'm going to take my tissue paper and I'm going to take my tissue paper. | [動画](../Uni-Sign/outputs/20260912-self-03-06-preprocessed-r1/04_i_want_soap_vertical/reencode.avi) | [骨格](../Uni-Sign/outputs/20260912-self-03-06-preprocessed-pose-overlays-r1/04_i_want_soap_vertical/reencode/pose_overlay.mp4) |
| crop | You want to make sure that you're getting the right amount of glue on the top and the bottom. | [動画](../Uni-Sign/outputs/20260912-self-03-06-preprocessed-r1/04_i_want_soap_vertical/crop.avi) | [骨格](../Uni-Sign/outputs/20260912-self-03-06-preprocessed-pose-overlays-r1/04_i_want_soap_vertical/crop/pose_overlay.mp4) |
| crop＋縮小 | And I'm going to take my hand and I'm going to make a circle here. | [動画](../Uni-Sign/outputs/20260912-self-03-06-preprocessed-r1/04_i_want_soap_vertical/crop_resize.avi) | [骨格](../Uni-Sign/outputs/20260912-self-03-06-preprocessed-pose-overlays-r1/04_i_want_soap_vertical/crop_resize/pose_overlay.mp4) |
| crop＋余白＋縮小 | And you're going to say you're heavy, you're going to want to take your cake. | [動画](../Uni-Sign/outputs/20260912-self-03-06-preprocessed-r1/04_i_want_soap_vertical/crop_pad_resize.avi) | [骨格](../Uni-Sign/outputs/20260912-self-03-06-preprocessed-pose-overlays-r1/04_i_want_soap_vertical/crop_pad_resize/pose_overlay.mp4) |

### 05_i_want_water_horizontal

GT：`I want water.`

| 条件 | 未補正の予測英文 | 入力動画 | 骨格 |
|---|---|---|---|
| 原動画 | She's going to carry her mouth in a row. | [動画](../../../../data/sign/05_i_want_water_horizontal/original.mp4) | [骨格](../Uni-Sign/outputs/20260912-self-03-06-preprocessed-pose-overlays-r1/05_i_want_water_horizontal/original/pose_overlay.mp4) |
| 再保存対照 | She's going to carry her mouth in a row. | [動画](../Uni-Sign/outputs/20260912-self-03-06-preprocessed-r1/05_i_want_water_horizontal/reencode.avi) | [骨格](../Uni-Sign/outputs/20260912-self-03-06-preprocessed-pose-overlays-r1/05_i_want_water_horizontal/reencode/pose_overlay.mp4) |
| crop | I've got a heavy mouthpiece. | [動画](../Uni-Sign/outputs/20260912-self-03-06-preprocessed-r1/05_i_want_water_horizontal/crop.avi) | [骨格](../Uni-Sign/outputs/20260912-self-03-06-preprocessed-pose-overlays-r1/05_i_want_water_horizontal/crop/pose_overlay.mp4) |
| crop＋縮小 | I've got a heavy mouthpiece. | [動画](../Uni-Sign/outputs/20260912-self-03-06-preprocessed-r1/05_i_want_water_horizontal/crop_resize.avi) | [骨格](../Uni-Sign/outputs/20260912-self-03-06-preprocessed-pose-overlays-r1/05_i_want_water_horizontal/crop_resize/pose_overlay.mp4) |
| crop＋余白＋縮小 | I want it to be a little bit longer. | [動画](../Uni-Sign/outputs/20260912-self-03-06-preprocessed-r1/05_i_want_water_horizontal/crop_pad_resize.avi) | [骨格](../Uni-Sign/outputs/20260912-self-03-06-preprocessed-pose-overlays-r1/05_i_want_water_horizontal/crop_pad_resize/pose_overlay.mp4) |

### 06_i_want_water_vertical

GT：`I want water.`

| 条件 | 未補正の予測英文 | 入力動画 | 骨格 |
|---|---|---|---|
| 原動画 | They're going to dry out a little bit longer. | [動画](../../../../data/sign/06_i_want_water_vertical/original.mp4) | [骨格](../Uni-Sign/outputs/20260912-self-03-06-preprocessed-pose-overlays-r1/06_i_want_water_vertical/original/pose_overlay.mp4) |
| 再保存対照 | They're going to dry out a little bit longer. | [動画](../Uni-Sign/outputs/20260912-self-03-06-preprocessed-r1/06_i_want_water_vertical/reencode.avi) | [骨格](../Uni-Sign/outputs/20260912-self-03-06-preprocessed-pose-overlays-r1/06_i_want_water_vertical/reencode/pose_overlay.mp4) |
| crop | You're going to want to make sure that you're getting the right desired length. | [動画](../Uni-Sign/outputs/20260912-self-03-06-preprocessed-r1/06_i_want_water_vertical/crop.avi) | [骨格](../Uni-Sign/outputs/20260912-self-03-06-preprocessed-pose-overlays-r1/06_i_want_water_vertical/crop/pose_overlay.mp4) |
| crop＋縮小 | You're going to want to make sure that you're getting the right desired length. | [動画](../Uni-Sign/outputs/20260912-self-03-06-preprocessed-r1/06_i_want_water_vertical/crop_resize.avi) | [骨格](../Uni-Sign/outputs/20260912-self-03-06-preprocessed-pose-overlays-r1/06_i_want_water_vertical/crop_resize/pose_overlay.mp4) |
| crop＋余白＋縮小 | They're going to say it's heavy or thirsty. | [動画](../Uni-Sign/outputs/20260912-self-03-06-preprocessed-r1/06_i_want_water_vertical/crop_pad_resize.avi) | [骨格](../Uni-Sign/outputs/20260912-self-03-06-preprocessed-pose-overlays-r1/06_i_want_water_vertical/crop_pad_resize/pose_overlay.mp4) |


## 4. poseの独立検査

GT・生成文を使わず保存poseを集計した結果、全20条件でbody9・左右各手21・選択顔18点のscore≤0.3率は各0%。低信頼によるmask欠落は確認されないが、高scoreでも座標が正しいとは限らない。

肩幅/Wの原動画→crop→余白調整値は、03で0.2083→0.5046→0.4897、05で0.2077→0.5010→0.4909となり、参照中央値0.4911へ近づいた。04では0.1309→0.5844→0.3066、06では0.1284→0.6038→0.3020だった。縦動画では左右余白により人物占有率が再び小さくなり、**縦横比の一致と人物スケールの一致は別**だと分かる。鼻・肩のy/Hはほぼ不変。

03では原動画の保存poseに既に下端外の手点があり、今回の推論ではoriginal/reencode各125、crop119、crop_resize134、crop_pad_resize131点×frameだった。他3本は全条件0。今回のcropは全高さを保持しており、原画外の点を復元できない。score>0.3であることと画内にあることは異なる。これらの点のずれ・画外推定が誤訳へどの程度寄与したかは未確認。

今回分かったのは、幾何処理で生成内容や語句の一致は変わるものの、要求文の正訳には至らないこと。poseの正解座標との比較、確認済みposeを固定した後段の比較、同一入力の反復評価が引き続き必要で、データ側だけ・モデル側だけに原因を確定できない。

## 5. 実行と検証

How2Sign / SLT / pose-only、BF16、batch1、seed42、beam4、max_new_tokens100、max_length256、eval/no_gradを継続。モデルへは空GTを渡し、全20生成の完了後にのみラベルを採点用に読んだ。学習・ファインチューニング・文章補正なし。

上流revision `eed438bcb49e30405cd6ccdfcccca330c134e830`、重みSHA256 `1bfd5f3312f04e4736f0a52f4ef9535916e6de9676a2a0d00c708748683fb00d`、mT5 revision `2eb15465c5dd7f72a8f7984306ad05ebc3dd1e1f`。既存Uni-Sign環境、Python3.9.25、torch2.1.1+cu121、RTX A6000を使用。

20/20成功、40 ONNXセッションにCUDA provider、Missing/Unexpected keysとも0、全正規化入力・埋め込みが有限、全pose人数1。入力・pose・ラベルSHAを照合し、原動画・重み・過去結果を保持した。GPU終了後21MiB・使用率0%。20骨格動画も全フレームを再デコードして寸法・枚数・FPSを検証した。

サブエージェントは幾何設計/実施後pose集計、前処理補助の拡張、結果の独立解釈を分担。主担当がCPU変換・共有GPUの直列実行・可視化・統合を実施し、同じファイルの同時編集は避けた。依存・上流・重み変更、外部送信、Gitへの実データ追加なし。

## 6. 再現コマンドと保存先

作業ルートで実行。再実行時は保存先を新規名に変える。

```bash
conda run --no-capture-output -n Uni-Sign python -B \
  research/sign/uni-sign/scripts/preprocess_self_videos.py \
  --reference-manifest research/sign/uni-sign/Uni-Sign/outputs/20260912-how2sign-benchmark-download-r2/manifest.json \
  --evaluation-results research/sign/uni-sign/Uni-Sign/outputs/20260912-self-03-06-evaluation-r1/results.json \
  --output-dir research/sign/uni-sign/Uni-Sign/outputs/20260912-self-03-06-preprocessed-r1

conda run --no-capture-output -n Uni-Sign python -B \
  research/sign/uni-sign/scripts/evaluate_preprocessed_self.py \
  --manifest research/sign/uni-sign/Uni-Sign/outputs/20260912-self-03-06-preprocessed-r1/manifest.json \
  --output-dir research/sign/uni-sign/Uni-Sign/outputs/20260912-self-03-06-preprocessed-evaluation-r1

/home/kosaki/anaconda3/envs/Uni-Sign/bin/python -B \
  research/sign/uni-sign/scripts/render_native_pose_overlays.py \
  --results research/sign/uni-sign/Uni-Sign/outputs/20260912-self-03-06-preprocessed-evaluation-r1/results.json \
  --output-dir research/sign/uni-sign/Uni-Sign/outputs/20260912-self-03-06-preprocessed-pose-overlays-r1 \
  --all-variants
```

- [前処理manifest](../Uni-Sign/outputs/20260912-self-03-06-preprocessed-r1/manifest.json)：16派生動画、固定仕様、全画素検証とSHA。同階層に推論前の`planned_manifest.json`。
- [全20推論結果と個別・集計スコア](../Uni-Sign/outputs/20260912-self-03-06-preprocessed-evaluation-r1/results.json)：同階層に実行manifest、command、environment、inference.log。各ID/条件以下にpose・予測英文。
- [全20骨格動画manifest](../Uni-Sign/outputs/20260912-self-03-06-preprocessed-pose-overlays-r1/manifest.json)：全フレームの検証とSHA。各ID/条件以下に`pose_overlay.mp4`・`preview.jpg`。
- [最終照合](../Uni-Sign/outputs/20260912-self-03-06-preprocessed-analysis-r1/verification.json)と同階層の`verify_results.py`。
- [独立設計・pose調査](../Uni-Sign/outputs/20260912-self-03-06-preprocess-design-r1/note.md)：同階層に設計値・実施後pose集計・CPU再現コード・代表画像。

変更ファイルは[preprocess_self_videos.py](../scripts/preprocess_self_videos.py)（既存評価結果のpose読込と新モードの左右padding）、[render_native_pose_overlays.py](../scripts/render_native_pose_overlays.py)（全前処理条件の描画）、本報告と[README](../README.md)。以前のCLIモードは維持し、推論・採点補助自体には今回の変更なし。

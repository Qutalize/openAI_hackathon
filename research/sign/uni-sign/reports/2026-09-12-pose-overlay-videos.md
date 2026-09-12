# 保存poseの動画重ね合わせ（2026-09-12）

前回の[自前動画前処理評価](2026-09-12-self-preprocessing-evaluation.md)で実際に推論へ使用した保存poseを、対応する映像へ重ねた動画10本を作成した。poseの再推定・英文の再生成・採点の変更はしていない。CPU描画のみで、GPU、追加依存、外部送信は使用していない。

## 動画

保存先は`research/sign/uni-sign/Uni-Sign/outputs/20260912-self-pose-overlays-r1/`。

| 条件 | 01：名前の質問 | 02：挨拶 |
|---|---|---|
| 原動画 | [動画](../Uni-Sign/outputs/20260912-self-pose-overlays-r1/01_whats_your_name/original/pose_overlay.mp4) | [動画](../Uni-Sign/outputs/20260912-self-pose-overlays-r1/02_greetings/original/pose_overlay.mp4) |
| 画素同一の再保存対照 | [動画](../Uni-Sign/outputs/20260912-self-pose-overlays-r1/01_whats_your_name/reencode/pose_overlay.mp4) | [動画](../Uni-Sign/outputs/20260912-self-pose-overlays-r1/02_greetings/reencode/pose_overlay.mp4) |
| crop | [動画](../Uni-Sign/outputs/20260912-self-pose-overlays-r1/01_whats_your_name/crop/pose_overlay.mp4) | [動画](../Uni-Sign/outputs/20260912-self-pose-overlays-r1/02_greetings/crop/pose_overlay.mp4) |
| crop＋縮小 | [動画](../Uni-Sign/outputs/20260912-self-pose-overlays-r1/01_whats_your_name/crop_resize/pose_overlay.mp4) | [動画](../Uni-Sign/outputs/20260912-self-pose-overlays-r1/02_greetings/crop_resize/pose_overlay.mp4) |
| crop＋下余白＋縮小 | [動画](../Uni-Sign/outputs/20260912-self-pose-overlays-r1/01_whats_your_name/crop_pad_resize/pose_overlay.mp4) | [動画](../Uni-Sign/outputs/20260912-self-pose-overlays-r1/02_greetings/crop_pad_resize/pose_overlay.mp4) |

各動画の隣に中央フレームの`preview.jpg`を保存した。

## 表示の読み方

- 左側：対応動画へのpose重ね合わせ。右上：演者の左手、右下：演者の右手。それぞれ「Video」が骨格なし、「Pose overlay」が同じ領域の骨格あり。
- 水色は演者の左手、黄色は右手、緑は上半身、ピンクはモデルが選択する顔点。画面上の左右とは区別する。
- 赤い×：モデル使用点のうちscore≤0.3でマスクされる点の推定位置。線は両端のscoreが0.3を超え、画像内にある場合だけ描画。
- 灰色：推定された133点中、翻訳モデルが選択しない点。灰色点はscore>0.3かつ画像内の場合のみ表示。
- 画外点は画像の端へ寄せず、下欄の`outside image`で数える。`masked`とは重複し得る別の集計。
- 右側の拡大領域は、当該フレームの有効な手点の範囲へ余白を付けて決める。見やすさのための追従表示で、モデルへの入力変更ではない。有効点が3点未満なら拡大せずその旨を表示。
- ヘッダーのframe番号は0始まり。時刻はframe番号÷平均FPSの概算で、元の可変フレーム時刻そのものではない。

描画するのは**正解poseではなく推定pose**。scoreは座標の正しさの確率ではない。映像に重なって見えることだけで、手話の意味に必要な指形・運動が正しいと判断しない。この可視化自体は誤訳原因の確定や精度改善を示すものではない。

## 座標対応と検証

`online_inference.py`が保存したx/W,y/Hを、各条件の実際の動画幅・高さで画像座標へ復元した。crop後のposeに原動画の寸法を掛けることはしていない。部位別正規化前の座標を表示している。

モデル使用点は`datasets.py`と照合した計69点：body `[0,3,4,5,6,7,8,9,10]`、左手`91..111`、右手`112..132`、顔`[23,25,27,29,31,33,35,37,39,83..90,53]`。手指はCOCO133の接続を用いた。上半身・顔の線は見やすい解剖学的接続を描くもので、モデル内部graphの全接続を表示するものではない。

入力動画・保存poseのSHA256を推論結果と照合してから描画した。全10動画を再デコードし、01は各121フレーム、02は各155フレーム、1536×864、入力平均FPSとの誤差0.01未満を確認した。フレーム追加・削除なし、音声なし。MP4のcodecは既存OpenCVで利用可能だった`mp4v`（MPEG-4 Part 2）。元映像・poseは保持しており、可視化MP4は閲覧用の非可逆圧縮で、再推論用入力ではない。ブラウザによってはcodecが非対応のため、その場合はローカルの動画プレイヤーで開く。

主担当と独立担当が01原動画・02余白追加条件のpreviewで表示配置を確認。独立担当が使用点・左右・指接続・座標復元方法もコードで照合し、全体的な描画位置のずれや凡例との矛盾は見つからなかった。一部の手指では映像と推定線・点の不一致が見えるが、手指の正解座標との定量評価や、誤訳への寄与の検証は行っていない。

## 再現

作業ルートで実行。出力先は新規ディレクトリのみ使用できるため、再実行時は名前を変更する。

```bash
/home/kosaki/anaconda3/envs/Uni-Sign/bin/python -B \
  research/sign/uni-sign/scripts/render_pose_overlays.py \
  --results research/sign/uni-sign/Uni-Sign/outputs/20260912-self-preprocessed-evaluation-r1/results.json \
  --output-dir research/sign/uni-sign/Uni-Sign/outputs/20260912-self-pose-overlays-r1
```

新規コード：[render_pose_overlays.py](../scripts/render_pose_overlays.py)。保存先直下の`command.txt`に実行コマンド、[manifest.json](../Uni-Sign/outputs/20260912-self-pose-overlays-r1/manifest.json)に入力・出力SHA、描画条件、環境、全フレームのmask/画外点数と検証結果を記録した。動画・画像・poseはGitへ追加していない。

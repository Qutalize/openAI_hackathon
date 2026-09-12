# 自前ASL動画の画角前処理と再評価（2026-09-12）

自前2本に対し、固定crop・縮小・下余白追加を実施し、原動画と再保存対照を含む5条件×2本を同じHow2Sign pose-onlyモデルで推論した。**10/10件で英文生成は成功したが、正解の質問・挨拶を伝える翻訳は得られなかった。今回の前処理による翻訳改善は確認できない。**

肩幅や顔の配置は参照How2Signに近づいた。一方、手の低信頼点の割合は改善せず、01では増えた。ドメイン差は引き続き原因候補だが、画角を近づけるだけで解消する問題とは確認できなかった。コード・姿勢抽出経路の再現性とモデル性能の限界も残る。

## 1. 対象・分担・制約

- 入力はユーザー確認済みのASL（米国手話）、出力は英文。正解は各動画ディレクトリの`script.txt`。
- 01：`What's your name?`、02：`Nice to meet you. How are you?`。実演の個々の形・区間境界の独立確認は未実施。
- A：既存pose・映像から幾何条件を設計し、実施後もGT・予測を使わず配置とmaskを独立集計。
- B：比較条件、正解混入、数値の解釈を独立レビュー。
- C：前処理条件を直列に推論・採点する補助を実装。主担当がmanifest/SHA検証を追加して確認。
- 主担当：前処理補助の実装、CPU動画変換、共有GPU上の直列推論、成果物照合と統合。担当間の同時ファイル編集なし。
- 元動画・原稿・重み・過去結果の上書きなし。学習、ファインチューニング、新規checkpoint、依存変更、文章補正、外部への動画・顔・ランドマーク送信なし。

## 2. 前処理の仮説と固定した条件

参照は[前回取得したHow2Sign test 12本](2026-09-12-how2sign-test-subset.md)。配布poseの動画寸法から、W/H中央値0.7604、高さ中央値572を計算した。これは少数参照の代表値であり、学習データ全体の分布や上流指定の必須入力寸法ではない。

自前動画は1920×1080で横の背景が広く、肩幅/Wは約0.27だった。参照中央値は約0.49。左右背景を削ることで人物の占有率を近づけ、さらに下に余白を足す条件で顔・肩の正規化高さを近づける仮説を立てた。

| 条件ID | 処理 | 01の出力寸法 W×H | 02の出力寸法 W×H |
|---|---|---:|---:|
| original | 原動画を今回の実行系で再推論 | 1920×1080 | 1920×1080 |
| reencode | 画素を保持するFFV1再保存対照 | 1920×1080 | 1920×1080 |
| crop | 左右背景を固定crop、上下を保持 | 1142×1080 | 1222×1080 |
| crop_resize | crop後、高さ572へ縮小 | 604×572 | 648×572 |
| crop_pad_resize | crop後、下余白で縦横比を合わせて縮小 | 434×572 | 434×572 |

crop位置は01 `(x=422,y=0,w=1142,h=1080)`、02 `(458,0,1222,1080)`。元動画に対応する既存poseの全フレームから、score>0.3の上半身・顔・両手点の水平包絡を求め、両端に包絡幅の5%の余白を付けた。フレームごとの追跡cropによる見かけの運動を加えず、1本を通して同じ矩形とした。上下は切っていない。

下余白は灰色BGR=(114,114,114)、01は422行、02は528行。その後`INTER_AREA`で縮小した。縦横比を保つ意図で出力幅を偶数に丸めているため、丸めによる小差がある。余白は写っていない腕・手・胴体の復元ではない。pose-onlyモデルなので、背景を緑に置換する処理は採用しなかった。

鏡像反転はしていない。「左手が画面右に来る」というユーザーの説明は対面の非鏡像表示と整合し、反転が必要とする根拠がない。短い手話の境界を動きの少なさだけで判断できないため、時間trim、速度変更、フレーム削除・追加も行わなかった。

条件は推論前に`planned_manifest.json`へ固定した。参照manifestから使用したのはposeのパス・寸法で、正解文や予測を使った条件探索はしていない。

## 3. 入出力と実行の確認

- FFmpegコマンドは未導入だったため、既存OpenCVのFFV1 AVI書き出しを利用。追加インストールなし。
- 8派生動画すべてを再デコードし、全フレームが予定した画像変換と完全一致（最大画素差0）。`reencode`は元動画のデコード画素そのものと全フレーム一致。
- 01は121、02は155フレームを順序どおり保存・使用。最大256による間引きなし。
- AVIには元動画の平均FPSを用いた固定FPSで保存した（約30.245 / 30.308）。元の可変フレーム時刻を厳密に保持したものではない。今回の上流pose-only入力はフレーム列を使い、各フレームの時刻をモデルへ渡さない。
- 元動画のSHA256は既存pose抽出時の入力記録と一致。派生動画・pose・実行スクリプトのSHAも保存記録と照合した。
- 代表フレームを目視し、新たな手・顔の切断がないことを確認。全フレームでは高信頼点包絡を保持する設計だが、未検出の点まで見切れがないと保証するものではない。
- 各条件で人物数1、正規化入力とモデル埋め込みは有限。20個のONNXセッションすべてに`CUDAExecutionProvider`あり。
- checkpoint strict読込のMissing/Unexpected keysはともに0。翻訳信頼度はモデルから提供されず`null`。

共通設定はHow2Sign / SLT / pose-only、BF16、batch 1、seed 42（条件ごとに再設定）、beam 4、max_new_tokens 100、max_length 256。全推論でモデルへのGTは空文字列とし、10件の生成が終了した後にのみ正解ラベルを採点用に読んだ。

上流revisionは`eed438bcb49e30405cd6ccdfcccca330c134e830`、How2Sign重みSHA256は`1bfd5f3312f04e4736f0a52f4ef9535916e6de9676a2a0d00c708748683fb00d`。mT5 revisionは`2eb15465c5dd7f72a8f7984306ad05ebc3dd1e1f`。既存conda `Uni-Sign`、Python 3.9.25、torch 2.1.1+cu121、RTX A6000を使用。全依存と設定は実行出力の`environment.txt`・`manifest.json`に保存した。

## 4. 採点結果

2本をまとめたcorpus BLEU-4、ROUGE-L Fの平均、補助WER。同じ[既存採点補助](../scripts/score_saved_results.py)を使用した。BLEU/ROUGEは0–100で高い方が良く、正解率（Accuracy）ではない。WERは置換・削除・挿入の最小語編集数÷GT語数×100で低い方が良く、余計な語が多いと100%を超える。

| 条件 | 本数 | BLEU-4 ↑ | ROUGE-L ↑ | WER % ↓ | 完全一致 |
|---|---:|---:|---:|---:|---:|
| 原動画・今回再実行 | 2 | 2.01 | 5.56 | 200.00 | 0/2 |
| 画素同一の再保存対照 | 2 | 2.35 | 5.56 | 170.00 | 0/2 |
| crop | 2 | 2.56 | 0.00 | 170.00 | 0/2 |
| crop＋縮小 | 2 | 2.65 | 6.25 | 170.00 | 0/2 |
| crop＋下余白＋縮小 | 2 | 2.10 | 0.00 | 170.00 | 0/2 |

BLEUは上流の13a tokenization、case mixed、exponential smoothing。特に短い2文では、一部の単語一致や平滑化・予測長の影響が強い。WERのGTは小文字化、句読点除去、語中apostrophe保持で計10語。今回baselineは20編集/10語、他条件は17編集/10語だった。翻訳の適切な言い換えにもWERは罰点を付けるため補助指標とする。

**BLEU-4の最高2.65を翻訳改善とは解釈しない。** 全10文がGTの質問・挨拶の主旨と異なり、WER低下は画角を変えない再保存対照でも生じている。前処理条件のWERは対照から改善していない。前回報告の原動画BLEU-4 2.35 / WER170%は過去の保存結果であり、今回の再実行2.01 / 200%と区別する。

前回のHow2Sign test 12組は配布pose BLEU-4 14.96、同じ動画のオンライン再抽出12.83だった。自前の2文と文長・内容・件数が異なるため、差をそのままドメイン差の因果効果と扱うことはできない。

## 5. GTと全予測英文

01 GT：`What's your name?`

| 条件 | 予測（未補正） |
|---|---|
| original | I'm just going to hold it for a little bit longer. |
| reencode | We're going to choose a smaller weight strainer. |
| crop | I'm going to scale it down to a smaller size. |
| crop_resize | I'm going to take all the weight here. |
| crop_pad_resize | We're going to raise it up to what's called a serving. |

02 GT：`Nice to meet you. How are you?`

| 条件 | 予測（未補正） |
|---|---|
| original | There's a nice little note cards that you can play with. |
| reencode | There's a nice little note cards that you can play with. |
| crop | They're nice and really interesting. |
| crop_resize | And that's a nice note to keep in mind. |
| crop_pad_resize | They're nice and different kinds of comics. |

## 6. 幾何は近づいたか、姿勢抽出は改善したか

独立担当が保存された再抽出poseから集計。座標は画像のW/Hで正規化し、各動画内の中央値。参照は12動画の中央値。

| 指標 | How2Sign参照 | 01原動画→crop_pad_resize | 02原動画→crop_pad_resize |
|---|---:|---:|---:|
| 肩幅/W | 0.4911 | 0.2710→0.4597 | 0.2758→0.4394 |
| 鼻y/H | 0.2064 | 0.3674→0.2653 | 0.3488→0.2355 |
| 肩中心y/H | 0.4193 | 0.6324→0.4534 | 0.6217→0.4160 |
| 手点mask率 | 0%（配布pose） | 8.97%→14.46% | 5.01%→5.42% |

肩の占有幅、鼻と肩の位置は参照へ近づいた。しかし手点maskは改善せず、01はcropだけでも13.93%へ増えた。顔の選択18点のmask率は全条件0%。mask率は全フレームの手点42個中score≤0.3の割合であり、実際の座標誤差・検出精度・翻訳信頼度・確率ではない。配布poseとの比較には抽出器や後処理の差も含まれる。

`datasets.py`の`load_part_kp`・`crop_scale`は画像幅/高さで正規化した座標をさらに部位別に処理する。共通の拡大・移動は多くが吸収される一方、幅だけを変えるcropや高さを変えるpaddingはx/yの座標比にも作用する。今回は動画を加工してposeを再抽出したため、座標変換の効果と姿勢検出器への作用は分離できていない。

原動画と全画素同一の再保存対照でも01の予測は異なり、保存poseにも座標・scoreの差があった。これは画像圧縮による情報損失では説明できない。実行ごとに姿勢を再抽出する経路の再現性が残課題であり、16threadやORTの特定挙動が原因と確定したわけではない。前回の固定pose反復では同条件の出力が一致したが、今回の全条件を複数反復した分散評価はしていない。

## 7. 原因候補と次の優先順位

| 仮説 | 今回分かったこと | 判定 |
|---|---|---|
| 人物が小さく、画角が参照と違うため失敗 | 配置を近づけても正しい質問・挨拶は得られず | 差は確認。今回の補正だけでは不足 |
| crop/縮小で手の姿勢抽出が改善する | 低信頼maskは改善せず、01は増加 | 改善を支持しない。座標精度の正解評価は未実施 |
| 動画再保存の非可逆圧縮が結果を変えた | 対照の全画素は一致、それでも01の出力が変化 | 今回の対照差の説明として否定 |
| 最大256フレームの間引きが原因 | 121/155フレームを全条件で全て使用 | 今回の原因ではない |
| checkpoint不整合・CUDA不使用・NaN | SHA、strict keys、全20 CUDA sessions、有限値を確認 | これらの不具合は見つからず。コード全体の正しさの証明ではない |
| 語彙・表現・文長・撮影条件など広いドメイン差 | 空間的補正ではこれらを一致させられない | 原因候補として残る |
| 再抽出の変動とモデルの入力感度 | 同じ画素から異なるpose・生成文を確認 | 現象は確認。特定の実装原因と寄与率は未確定 |

学習なしで次に切り分けるなら、次の順が有用。いずれも今回未実施。

1. **保存poseへの座標変換だけで比較し、各poseを固定して反復する。** 動画再抽出を避けた条件でcrop/paddingの幾何効果を分ける。次に同一動画の再抽出反復で変動幅を測り、小さなスコア差を効果と誤認しないようにする。
2. **手が動く区間の骨格を重ねて確認する。** ASLを読める人と手形・左右・遮蔽・開始終了を確認し、maskの増加が意味に関わる区間かを調べる。単に動きが少ないという理由でtrimしない。
3. **同じASL内容を、手指と上半身が全区間写る画角で撮り直して比較する。** 今回のcropは撮影時の遮蔽や画外情報を復元できない。元動画を残して同じ内容で比較する。

今回のデータだけで、crop_resizeを「推奨・高精度な前処理」として採用する根拠はない。ドメイン差が原因の一部である可能性は残るが、データだけ・コードだけの二択で結論する段階ではない。

## 8. 再現コマンドと成果物

作業ルートで実行したコマンド。出力先は既存の場合エラーになるため、再実行時は両方の出力先を新規名に変える。既存参照manifest・pose・重みを使用し、ダウンロード不要。

```bash
conda run --no-capture-output -n Uni-Sign python -B \
  research/sign/uni-sign/scripts/preprocess_self_videos.py \
  --reference-manifest research/sign/uni-sign/Uni-Sign/outputs/20260912-how2sign-benchmark-download-r2/manifest.json \
  --pose-dir research/sign/uni-sign/Uni-Sign/outputs/20260912-mismatch-diagnostic-r1 \
  --output-dir research/sign/uni-sign/Uni-Sign/outputs/20260912-self-preprocessed-r1

conda run --no-capture-output -n Uni-Sign python -B \
  research/sign/uni-sign/scripts/evaluate_preprocessed_self.py \
  --manifest research/sign/uni-sign/Uni-Sign/outputs/20260912-self-preprocessed-r1/manifest.json \
  --output-dir research/sign/uni-sign/Uni-Sign/outputs/20260912-self-preprocessed-evaluation-r1
```

追加・変更ファイル：

- [preprocess_self_videos.py](../scripts/preprocess_self_videos.py)：固定条件の決定、lossless動画生成、全画素照合。
- [evaluate_preprocessed_self.py](../scripts/evaluate_preprocessed_self.py)：入力SHA検証、5条件の直列推論、生成後の採点。
- 本報告書と[README](../README.md)。上流コード・依存・重みに今回の変更なし。

生生成物（すべて`Uni-Sign/outputs/`内、Git追加・外部送信なし）：

- [前処理済み動画とmanifest](../Uni-Sign/outputs/20260912-self-preprocessed-r1/)：各動画ID以下に4種類の`.avi`と比較画像。`planned_manifest.json`に推論前の条件を保存。
- [全予測・個別/集計スコア](../Uni-Sign/outputs/20260912-self-preprocessed-evaluation-r1/results.json)：各条件の下に`prediction.txt`、`result.json`、`online_pose.pkl`。
- [実行設定](../Uni-Sign/outputs/20260912-self-preprocessed-evaluation-r1/manifest.json)、同階層の`command.txt`、`environment.txt`、`inference.log`。
- [最終照合結果](../Uni-Sign/outputs/20260912-self-preprocessed-evaluation-r1/verification.json)と同階層の`verify_artifacts.py`。保存pixel検査、実ファイルSHA、全10件の有限値・frame使用を確認して成功。GPU終了後は24 MiB、使用率0%。
- [独立した幾何調査](../Uni-Sign/outputs/20260912-preprocess-design-a/design.md)、同階層の`geometry.json`、`post_extraction_geometry.json`、CPU集計スクリプト。
- [比較設計レビュー](../Uni-Sign/outputs/20260912-preprocess-protocol-b/protocol-review.md)。最終結論も担当間で相互確認し、maskを精度と扱う断定や、指標微増を翻訳改善と扱う解釈を除いた。

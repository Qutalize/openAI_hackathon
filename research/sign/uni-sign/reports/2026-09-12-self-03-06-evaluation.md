# 追加動画03〜06：石けん・水の要求文を再評価

既存のHow2Sign pose-onlyモデルで追加原動画4本を推論・採点した。**4/4件で英文生成は成功したが、`I want soap.` / `I want water.`の意味を伝える翻訳は得られなかった。**

追加検査で、verticalの2本も実際には1280×720の横長ファイルで、中央の縦映像に左右の黒帯が付いていると判明した。そこで黒帯だけを除いた動画を作成し、原動画再実行と比較した。06では`want`・`water`が予測に現れたが別の指示文となり、正訳にはならなかった。

今回の使用pose点は全8推論条件でscore>0.3だった。以前の01/02と異なり、低信頼でマスクされる点は見つからなかった。**これはposeの正確さの証明ではないが、「低信頼で手点が消えたこと」が今回の失敗を説明する証拠はない。**

## 1. 入力と比較の範囲

入力言語はこれまでの会話のASL前提を継続、出力は英文。正解参照は各`data/sign/<id>/script.txt`を使用した。新4本の実演・個々の指形を手話話者が独立確認したものではない。データREADMEには未確認・暫定原稿という記載も残るため、数値は提供原稿との一致度として報告する。

| ID | 撮影区分 | 参照英文 | デコード寸法 | フレーム | 秒（frame/30） |
|---|---|---|---:|---:|---:|
| 03 | horizontal | I want soap. | 1280×720 | 127 | 4.233 |
| 04 | vertical | I want soap. | 1280×720 | 103 | 3.433 |
| 05 | horizontal | I want water. | 1280×720 | 89 | 2.967 |
| 06 | vertical | I want water. | 1280×720 | 109 | 3.633 |

全4本30fps、正立。各7時点の映像確認では人物1人で、顔・動作中の手の明白な見切れは見られなかった。横動画で膝に置いた手は下端へ接近する。回転metadataは0、OpenCVの自動回転を無効にしても初フレームが一致し、回転は加えていない。

横・縦は長さと動作タイミングが異なる別入力であり、同じ動画に回転・画角変更だけを施した対照ではない。横のスコアが高くても、撮影方向だけが原因とは言えない。

## 2. 原動画4本の結果

すべて未補正のモデル出力。

| ID | 予測英文 | BLEU-4 ↑ | ROUGE-L ↑ | WER % ↓ |
|---|---|---:|---:|---:|
| 03 | I'm going to say I'm going to rinse it down a little bit. | 2.84 | 0.00 | 433.33 |
| 04 | I'm going to take my tissue paper and I'm going to take my tissue paper. | 2.45 | 0.00 | 500.00 |
| 05 | I'm going to carry it to a boil. | 4.77 | 0.00 | 266.67 |
| 06 | I'm going to turn the red bottom up a little bit. | 3.39 | 0.00 | 366.67 |

| 集計対象 | 本数 | corpus BLEU-4 ↑ | ROUGE-L ↑ | WER % ↓ | 完全一致 |
|---|---:|---:|---:|---:|---:|
| 追加原動画すべて | 4 | 1.12 | 0.00 | 391.67 | 0/4 |
| horizontal（03/05） | 2 | 2.12 | 0.00 | 350.00 | 0/2 |
| vertical・黒帯付き（04/06） | 2 | 1.69 | 0.00 | 433.33 | 0/2 |

BLEU/ROUGEは正解率ではない。[既存採点補助](../scripts/score_saved_results.py)を使用し、BLEUは上流の13a tokenization・case mixed・exponential smoothing、ROUGE-LはF平均×100。集計BLEUは文別BLEUの平均ではない。短文では平滑化や部分一致の影響が大きい。

WERは小文字化・句読点除去・語中apostrophe保持の語編集距離÷GT語数×100。今回のGTは各3語で計12語、編集数は計47なので391.67%。長い無関係な文の挿入が多いため100%を超える。適切な言い換えにも罰点が付く補助指標だが、今回の4文は単なる言い換えではなく要求の意味自体が不一致だった。

`rinse`と石けん、`boil`と水に話題上の関連があっても、「石けん／水がほしい」という要求の対象・意図を伝えていないため正訳扱いしない。

## 3. 縦動画の黒帯除去

独立担当がGT・予測を使わず、04/06の全フレームを検査。非zero画素の水平和集合は両方とも`[430,850)`で、外側の画素はすべて厳密に0だった。

両方に同じ固定crop `(x=430,y=0,w=420,h=720)`を適用。黒帯以外の非zero画素は1画素も落とさず、回転・縮小・時間trim・速度変更を加えていない。既存OpenCVのFFV1 AVIで保存し、全103/109フレームを再デコードして原動画の該当矩形と完全一致（最大画素差0）を確認した。仕様は推論前の`planned_manifest.json`に固定した。

再抽出の変動が既知のため、追加実行でも原動画を再推論した。04は最初の原動画と同じ文だったが、06の原動画は今回も別の文となった。

| ID | 条件 | 予測英文 |
|---|---|---|
| 04 | 原動画・追加実行 | I'm going to take my tissue paper and I'm going to take my tissue paper. |
| 04 | 黒帯除去 | And I'm going to say you want to take a piece of this. |
| 06 | 原動画・追加実行 | They're going to dry out a little bit longer. |
| 06 | 黒帯除去 | You're going to want to make sure that you're getting the right amount of water out of the tank. |

| 同じ追加実行内の比較 | 本数 | BLEU-4 ↑ | ROUGE-L ↑ | WER % ↓ | 完全一致 |
|---|---:|---:|---:|---:|---:|
| 原動画・再実行 | 2 | 1.84 | 0.00 | 400.00 | 0/2 |
| 黒帯除去 | 2 | 1.71 | 17.19 | 483.33 | 0/2 |

ROUGE上昇は語の一致が増えたことを反映する。06は`want`と`water`を含むが、タンクから適量の水を取り出すように促す別の指示で、`I want water.`の希望表明とは一致しない。04も`want`は出たが`soap`がない。長文化でWERは悪化した。**黒帯除去による翻訳改善は確認できない。** 原動画再実行自体も変化しており、単発結果から黒帯除去の単独効果や安定性は確定できない。

## 4. poseと原因について分かったこと

保存poseの独立集計では、原動画4件＋追加比較4件のすべてで、body9・左手21・右手21・選択顔18点のscore≤0.3率が各0%。したがって、この閾値による点の欠落は今回の失敗を説明しない。一方、高scoreでも指先・遮蔽部の位置が正しい保証はなく、正解poseとの定量比較は未実施。

| 指標 | 04 原動画→黒帯除去 | 06 原動画→黒帯除去 |
|---|---:|---:|
| 肩幅/W | 0.1309→0.3986 | 0.1284→0.3933 |
| 鼻y/H | 0.3437→0.3436 | 0.3446→0.3440 |
| 肩中心y/H | 0.4733→0.4731 | 0.4756→0.4759 |
| 手点mask率 | 0%→0% | 0%→0% |

横の正規化比は約3.05倍になり、画像幅の分母1280/420=3.0476と整合。yはほぼ不変で、意図した幾何変更は実現した。縦映像を横長canvasのまま入力した場合と、黒帯を除いた場合は、x/W,y/Hの比が異なる。姿勢抽出後の部位別正規化はこの縦横比の変化を完全には取り除かない。

現時点で否定・確認できる範囲：

- 回転の誤り、256フレーム上限による間引き、低信頼点のマスク、非有限値、重みkeys不整合、CUDA不使用は今回の失敗説明として支持されない。
- 黒帯による座標比の違いは確認したが、黒帯除去だけでは今回の失敗は解消しなかった。
- poseの正確さ、部位別正規化後の入力分布、後段モデルがこの短い要求文を扱う能力、再抽出の変動は引き続き検証対象。
- 「poseが正しいので後段だけが悪い」と結論できる段階ではない。次の切り分けは手話をしている区間の指先・手形の対応確認と、確認済みposeを固定した後段比較。

## 5. 実行条件・検証・分担

以前と同じHow2Sign / SLT / pose-only、BF16、batch1、seed42、beam4、max_new_tokens100、max_length256。モデルはeval、no_grad、checkpoint strict読み込み。入力フレームは全条件256未満なので全部使用した。原稿はモデルへ渡さず、各実行の全生成後にのみ採点用に読んだ。音声・LLMによる補正は使用していない。

上流revision `eed438bcb49e30405cd6ccdfcccca330c134e830`、重みSHA256 `1bfd5f3312f04e4736f0a52f4ef9535916e6de9676a2a0d00c708748683fb00d`、mT5 revision `2eb15465c5dd7f72a8f7984306ad05ebc3dd1e1f`。既存Uni-Sign環境、Python3.9.25、torch2.1.1+cu121、RTX A6000を使用。依存・上流コード・重みは変更していない。

主担当がGPU実行を直列調整。サブエージェントは入力幾何/黒帯境界、評価補助の小修正、GTと予測の解釈をそれぞれ独立に担当し、同じファイルを同時編集しなかった。

原動画4件・追加比較4件の計8件が成功。全16 ONNXセッションにCUDA provider、各実行Missing/Unexpected keysとも0、全入力正規化とモデル埋め込みが有限、pose人数1を確認。入力・pose・ラベル・実行スクリプトのSHAを記録と照合した。GPU終了後21MiB・使用率0%。

pose重ね合わせ動画も8件作成し、全フレームを再デコードしてframe数・FPS・1536×864の寸法を検証した。推論時の保存poseを再利用し、描画のための再推定はしていない。色や読み方は[前回の可視化説明](2026-09-12-pose-overlay-videos.md)と同じ。映像・顔・ランドマークを外部へ送信せず、元動画・原稿・既存結果を上書きしていない。

## 6. 動画・生結果

後続依頼により、拡大欄を付けず、元動画の画角・1280×720・30fpsのまま骨格を直接重ねる版も4本作成した。上記原動画評価の保存poseをそのまま使用し、再推定なし。黒帯を含めた元画角を維持、全フレームの再デコードで寸法・枚数・FPSを確認した。音声なし、閲覧用MP4（mp4v）。表示色・mask閾値は既存可視化と同じ。

| ID | 元画角の骨格オーバーレイ（拡大欄なし） |
|---|---|
| 03 soap horizontal | [動画](../Uni-Sign/outputs/20260912-self-03-06-native-pose-overlays-r1/03_i_want_soap_horizontal/original_pose_overlay.mp4) |
| 04 soap vertical | [動画](../Uni-Sign/outputs/20260912-self-03-06-native-pose-overlays-r1/04_i_want_soap_vertical/original_pose_overlay.mp4) |
| 05 water horizontal | [動画](../Uni-Sign/outputs/20260912-self-03-06-native-pose-overlays-r1/05_i_want_water_horizontal/original_pose_overlay.mp4) |
| 06 water vertical | [動画](../Uni-Sign/outputs/20260912-self-03-06-native-pose-overlays-r1/06_i_want_water_vertical/original_pose_overlay.mp4) |

追加コードは[render_native_pose_overlays.py](../scripts/render_native_pose_overlays.py)。保存先直下の`manifest.json`に入力・pose・出力SHAと検証値、`command.txt`に実行コマンドを保存した。

```bash
/home/kosaki/anaconda3/envs/Uni-Sign/bin/python -B \
  research/sign/uni-sign/scripts/render_native_pose_overlays.py \
  --results research/sign/uni-sign/Uni-Sign/outputs/20260912-self-03-06-evaluation-r1/results.json \
  --output-dir research/sign/uni-sign/Uni-Sign/outputs/20260912-self-03-06-native-pose-overlays-r1
```

原動画のpose重ね合わせ：

| ID | 動画 |
|---|---|
| 03 soap horizontal | [pose動画](../Uni-Sign/outputs/20260912-self-03-06-pose-overlays-r1/03_i_want_soap_horizontal/original/pose_overlay.mp4) |
| 04 soap vertical | [pose動画](../Uni-Sign/outputs/20260912-self-03-06-pose-overlays-r1/04_i_want_soap_vertical/original/pose_overlay.mp4) |
| 05 water horizontal | [pose動画](../Uni-Sign/outputs/20260912-self-03-06-pose-overlays-r1/05_i_want_water_horizontal/original/pose_overlay.mp4) |
| 06 water vertical | [pose動画](../Uni-Sign/outputs/20260912-self-03-06-pose-overlays-r1/06_i_want_water_vertical/original/pose_overlay.mp4) |

黒帯除去版：

| ID | 処理済み入力 | pose重ね合わせ |
|---|---|---|
| 04 | [remove_bars.avi](../Uni-Sign/outputs/20260912-self-04-06-remove-bars-r1/04_i_want_soap_vertical/remove_bars.avi) | [pose動画](../Uni-Sign/outputs/20260912-self-04-06-remove-bars-pose-overlays-r1/04_i_want_soap_vertical/remove_bars/pose_overlay.mp4) |
| 06 | [remove_bars.avi](../Uni-Sign/outputs/20260912-self-04-06-remove-bars-r1/06_i_want_water_vertical/remove_bars.avi) | [pose動画](../Uni-Sign/outputs/20260912-self-04-06-remove-bars-pose-overlays-r1/06_i_want_water_vertical/remove_bars/pose_overlay.mp4) |

追加比較の原動画再実行のpose動画は、上記remove-bars-pose-overlays保存先の各ID配下`original/pose_overlay.mp4`。

- [原動画4件の結果](../Uni-Sign/outputs/20260912-self-03-06-evaluation-r1/results.json)、[黒帯比較4件の結果](../Uni-Sign/outputs/20260912-self-04-06-remove-bars-evaluation-r1/results.json)。各保存先に`manifest.json`、`command.txt`、`environment.txt`、`inference.log`、各ID/variantの`prediction.txt`・`online_pose.pkl`。
- [検証と集計](../Uni-Sign/outputs/20260912-self-03-06-evaluation-r1/summary.json)、同階層の`verify_and_summarize.py`。
- [独立した入力・pose調査](../Uni-Sign/outputs/20260912-self-03-06-input-review-r1/note.md)、同階層の`probe.json`、`pose_comparison.json`、CPU再現スクリプトと代表画像。

## 7. 再現コマンド・変更

作業ルートで実行。保存先が存在する場合はエラーになるため、再実行時は新規名に変更する。

```bash
# 今回の4入力を固定したmanifest（準備済み。再作成は新規保存先のhelperで行う）
python3 -B research/sign/uni-sign/Uni-Sign/outputs/20260912-self-03-06-inputs-r1/prepare_manifest.py

conda run --no-capture-output -n Uni-Sign python -B \
  research/sign/uni-sign/scripts/evaluate_preprocessed_self.py \
  --manifest research/sign/uni-sign/Uni-Sign/outputs/20260912-self-03-06-inputs-r1/manifest.json \
  --output-dir research/sign/uni-sign/Uni-Sign/outputs/20260912-self-03-06-evaluation-r1

conda run --no-capture-output -n Uni-Sign python -B \
  research/sign/uni-sign/scripts/crop_vertical_black_bars.py \
  --manifest research/sign/uni-sign/Uni-Sign/outputs/20260912-self-03-06-inputs-r1/manifest.json \
  --sample-ids 04_i_want_soap_vertical 06_i_want_water_vertical \
  --output-dir research/sign/uni-sign/Uni-Sign/outputs/20260912-self-04-06-remove-bars-r1

conda run --no-capture-output -n Uni-Sign python -B \
  research/sign/uni-sign/scripts/evaluate_preprocessed_self.py \
  --manifest research/sign/uni-sign/Uni-Sign/outputs/20260912-self-04-06-remove-bars-r1/manifest.json \
  --output-dir research/sign/uni-sign/Uni-Sign/outputs/20260912-self-04-06-remove-bars-evaluation-r1

/home/kosaki/anaconda3/envs/Uni-Sign/bin/python -B \
  research/sign/uni-sign/scripts/render_pose_overlays.py \
  --results research/sign/uni-sign/Uni-Sign/outputs/20260912-self-03-06-evaluation-r1/results.json \
  --output-dir research/sign/uni-sign/Uni-Sign/outputs/20260912-self-03-06-pose-overlays-r1

/home/kosaki/anaconda3/envs/Uni-Sign/bin/python -B \
  research/sign/uni-sign/scripts/render_pose_overlays.py \
  --results research/sign/uni-sign/Uni-Sign/outputs/20260912-self-04-06-remove-bars-evaluation-r1/results.json \
  --output-dir research/sign/uni-sign/Uni-Sign/outputs/20260912-self-04-06-remove-bars-pose-overlays-r1
```

変更した管理対象ファイルは、追加sampleとoriginalのみの評価を安全に許可した[evaluate_preprocessed_self.py](../scripts/evaluate_preprocessed_self.py)、新規[crop_vertical_black_bars.py](../scripts/crop_vertical_black_bars.py)、本報告と[README](../README.md)。既存の描画・採点補助はそのまま使用した。診断の補助・生生成物はすべて`Uni-Sign/outputs`以下に保存し、Git追加はしていない。

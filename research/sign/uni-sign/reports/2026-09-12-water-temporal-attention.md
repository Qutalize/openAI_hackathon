# Uni-Sign：「I want water.」の誤訳に対する時間・内部特徴の診断

対象言語：ASL（ユーザー確認済み）→英語。対象は `06_i_want_water_vertical/crop_pad_resize` の1本。
実施日：2026-09-12。学習・重み更新・姿勢再抽出・文章補正は実施していない。

保存済みposeから **`They're going to say it's heavy or thirsty.` をtoken IDまで再現した**。
通常推論とAttention取得を有効にした推論も一致した。
両手を動かす区間を静止化すると、同じ文章の続きを条件とした `heavy` の対数確率が **6.992低下**、
口元の動きを含む区間を静止化すると `thir` が **2.108低下**した。
元の誤訳は入力特徴に依存している。一方、要求文を正しく符号化・生成している証拠にはならず、
静止系列・ゼロ映像埋め込みでも長い別の英文が生成された。

GTをteacher forcingした `water` の確率は **0.000200（約0.0200%、41位）**。
その直前の `I want` に対し、モデルは `to` を **23.32%** で優先した。
入力への依存を持ちながら、要求とは異なる語義と説明調の文へ進むことが今回の測定で確認できた。
姿勢抽出、学習済み視覚表現、文章側の学習傾向のどれが根本原因かは、この1本だけでは分離できていない。

## 成果物と読む順序

最終実行は [20260912-water-attention-r3](../Uni-Sign/outputs/20260912-water-attention-r3/)。
[ローカル図一覧HTML](../Uni-Sign/outputs/20260912-water-attention-r3/index.html)でも閲覧できる。
画像・骨格・中間特徴はローカルのGit対象外outputsに保存している。

1. [入力・骨格・予測・GTの共通時間軸](../Uni-Sign/outputs/20260912-water-attention-r3/figures/aligned_timeline.png)
2. [入力と保存骨格の対比](../Uni-Sign/outputs/20260912-water-attention-r3/figures/input_and_pose.png)、[手・顔の拡大](../Uni-Sign/outputs/20260912-water-attention-r3/figures/hands_detail.png)
3. [予測token](../Uni-Sign/outputs/20260912-water-attention-r3/figures/prediction_token_heatmap.png)／[予測単語](../Uni-Sign/outputs/20260912-water-attention-r3/figures/prediction_word_heatmap.png)、[GT token](../Uni-Sign/outputs/20260912-water-attention-r3/figures/gt_token_heatmap.png)／[GT単語](../Uni-Sign/outputs/20260912-water-attention-r3/figures/gt_word_heatmap.png)
4. [予測の層別図](../Uni-Sign/outputs/20260912-water-attention-r3/figures/prediction_layers.png)、[GTの層別図](../Uni-Sign/outputs/20260912-water-attention-r3/figures/gt_layers.png)、[予測head別重心](../Uni-Sign/outputs/20260912-water-attention-r3/figures/prediction_head_centroids.png)、[GT head別重心](../Uni-Sign/outputs/20260912-water-attention-r3/figures/gt_head_centroids.png)
5. [入力介入とEOS確率](../Uni-Sign/outputs/20260912-water-attention-r3/figures/interventions_and_eos.png)、[中間特徴](../Uni-Sign/outputs/20260912-water-attention-r3/figures/feature_diagnostics.png)

![同一時間軸による照合](../Uni-Sign/outputs/20260912-water-attention-r3/figures/aligned_timeline.png)

上図の時刻はencoder位置の由来となるフレームのアンカー。動作の正解時刻ではない。
Attentionは映像109位置内で再正規化し、色上限0.035で表示している。
prompt質量を含む元のAttentionは別のtoken／単語図とCSVに残した。
画像帯の各画像中心は0.2、0.6、…、3.4秒、画像幅は表示上の区画であり動作区間ではない。

## 1. 既存記録と実際の推論経路

必須のプロジェクト文書、モデルREADME、既存の[前処理比較](2026-09-12-self-03-06-preprocessing-comparison.md)、
[翻訳不一致調査](2026-09-12-how2sign-mismatch-investigation.md)、関連スクリプト・manifestを確認した。
過去の他動画ではpose抽出条件・演算精度で文が変化したため、今回は保存poseを固定した。

対象成果物を作った入口は `scripts/evaluate_preprocessed_self.py` のworker。
`demo.online_inference.main()`を直接動かした結果ではなく、上流の抽出・データセット・モデルをworkerが呼んだ結果である。
同スクリプトの現SHAは過去manifestと一致した。
`source` と空targetで `model(source, target)`、続けて `model.generate(max_new_tokens=100, num_beams=4)` を実行する。
空targetによる補助lossは計算されるが、生成へGTは渡らない。GTは全条件の生成終了後に採点だけで読む。

| 段階 | 実装・実条件 |
|---|---|
| 入力前処理 | 原動画からcrop `(514,0,274,720)`、左右137pxずつ灰色BGR114→548×720→INTER_AREAで436×572。trim、反転、順序変更なし |
| 人物検出 | 同梱RTMLib Wholebody `lightweight`、YOLOX-tiny、検出入力416×416 |
| 姿勢抽出 | RTMW-dw-l-m、入力192×256、wholebody133点、ONNX Runtime CUDA、16 thread。futuresは投入順で回収 |
| 今回再利用 | `online_pose.pkl` の109フレーム。上記ONNXは今回ロードも実行もしていない |
| 姿勢入力 | body9、left21、right21、face18の計69点、それぞれ `[x,y,score]`。RGB枝は無効 |
| 正規化 | bodyは全系列の高信頼点から中心・scale。手は各フレーム手首原点、顔は指定顔点原点、body由来scaleで除算。score≤0.3を0 |
| 空間処理 | 3→64 Linear、空間ST-GCNで256次元。左右手枝の重み共有。手へbody手首特徴、顔へbody鼻特徴を加算 |
| 時間処理 | 各部位にkernel5／stride1／padding2のtemporal ST-GCNを3段 |
| 接続 | 部位内の関節平均、4部位を特徴次元方向に連結して1024、`part_para`加算、Linear1024→768 |
| 文章処理 | How2Sign用checkpoint内の学習済みmT5-base encoder-decoder。encoder12層＋decoder12層、各12heads、d_model768 |
| tokenizer | T5Tokenizer、SentencePiece、`legacy=False`、pad／decoder-start=0、EOS=1 |

コード根拠：`Uni-Sign/datasets.py:18,83,337,606`、`models.py:80,139,195,260,268,313`、
`stgcn_layers/stgcn_block.py:69,118`、`demo/online_inference.py:70`、
`demo/rtmlib-main/rtmlib/tools/solution/wholebody.py:62`。
文章生成モデルを別の外部LLMに差し替えた解析ではない。

## 2. 入力整合性・再現条件・再現成否

入力・pose・GTのSHA256を再計算してresultと照合した。
prediction.txtの英文、選択フレーム番号も一致した。入力とoverlayを全フレームデコードし、両方109枚、436×572、30fpsを確認した。

| ファイル | 実測SHA256 |
|---|---|
| 入力AVI | `28d98a98c7b5740924df4ed8904bc1c0dd82126fa6734f1bb853af0f9c7b51eb` |
| 保存pose | `5a3b855859fa3cd2941c34ae57729645bcb4385bb13d8331e76f1aafbc5607b2` |
| GT | `613bf8875176ee3d25e5488081c33f59da417077746851150f643b805b1d419f` |
| How2Sign重み | `1bfd5f3312f04e4736f0a52f4ef9535916e6de9676a2a0d00c708748683fb00d` |

上流revision：`eed438bcb49e30405cd6ccdfcccca330c134e830`。
mT5取得revision：`2eb15465c5dd7f72a8f7984306ad05ebc3dd1e1f`。
実際の推論重みはstrictロードしたHow2Sign checkpoint全体であり、初期mT5重みだけの推論ではない。
現mT5構成・tokenizerファイルの全SHAは今回manifest、ONNXのSHAと既知上流patchは元評価のmanifestに保存されている。

Python3.9.25、torch2.1.1+cu121、Transformers4.40.0、NumPy1.22.4、SentencePiece0.1.97、OpenCV4.6.0。
RTX A6000を1プロセスで使用。eval／no_grad、BF16、batch1、seed42（Python／NumPy／Torch／CUDA）。
cuDNN deterministic=True、benchmark=False。checkpoint自体の浮動小数重みもBF16。
モデル精度を表す評価accuracyは本調査では測定しておらず、このBF16は演算精度の意味である。

生成はbeam4、samplingなし、max_new_tokens100、length_penalty1.0、early_stopping=False、
min_length0、min_new_tokensなし、forced EOSなし、repetition_penalty1.0。
設定ファイル内のmax_length20は今回のmax_new_tokens100で上書きされる。

| 検証 | 実測 |
|---|---|
| 保存poseからの通常生成 | 元の20 IDsと完全一致（decoder-start含む） |
| 固定入力での反復 | 完全一致 |
| 中間特徴hook前後の埋め込み最大絶対差 | 0 |
| Attention取得あり／なしの生成 | 全token完全一致 |
| 実生成beamのcross-attention対予測teacher forcing | 平均絶対差0.00004511、最大0.01171875 |
| 実生成transition対数確率対teacher forcing | 最大絶対差0.03987 |

Attentionは計算済み値を戻すフラグと読取hookだけで取得し、上流モデルを改変していない。
実生成はKV cacheとbeamを使い、teacher forcingは文を一括処理する。
また探索側はBF16 log_softmax、本診断スコアはlogitsをFP32へ変換したlog_softmaxなので、上の微差は両方の影響を含む。
実生成図には一括teacher forcingで代用したAttentionではなく、`beam_indices`から最終beamの祖先を追った実測値を使用した。

## 3. 時間位置の追跡と限界

動画長は109/30＝3.6333秒。最終フレームの時刻は108/30＝3.6000秒。
選択は0〜108すべて。`max_length256`によるランダム間引きは発生していない。
batch1で系列paddingは0枚、pose maskは109個すべて1。
畳み込みの時間strideはすべて1で、**109 pose位置→109特徴位置**を維持する。

固定prefixは次の8 IDsで、最後のEOSも有効な入力位置である。

```text
89349 ▁Translate / 11329 ▁sign / 17896 ▁language / 1552 ▁video /
288 ▁to / 5413 ▁English / 267 : / 1 </s>
```

mT5入力は `[1,117,768]`＝prefix8＋映像109。
encoder位置`8+j`のアンカーはフレーム`j`、`j/30`秒。
正規化済みposeに対する時間畳み込みの構造的受容野は
`max(0,j−6)..min(108,j+6)` の最大13フレーム。
例えばj54はf48〜60＝1.6〜2.0秒。端のConvはゼロpaddingであり、動画の追加フレームではない。
全109位置の受容野を独立したsupport伝播でも照合した。

ただし、生poseの正規化中心・scaleは全時系列から求めるため、生座標への依存は厳密な局所13枚だけではない。
さらにmT5 encoderの非因果self-attentionでprefixを含む117位置が混合される。
cross-attentionのkeyは混合後の表現で、**Attentionのピーク時刻＝その語を実演した時刻、とはならない**。
prefix位置も映像文脈を取り込むため、prefixへのAttentionを「映像に依存しない割合」と呼べない。

[時間対応JSON](../Uni-Sign/outputs/20260912-water-attention-r3/time_mapping.json)に位置、秒、受容野、境界paddingを記録した。
部位を関節平均・連結・Linearで混合するため、decoder cross-attention単体には「左右手別」「指別」の軸はない。
部位依存は後述の入力介入で調べる。

## 4. 動画上の観察とGT・予測の参照分布

入力から6フレーム間隔の連続画像、入力と保存overlayの同時刻対比、手・顔の拡大を実際に目視した。
以下は観察と診断窓であり、ASL専門家による語の境界アノテーションではない。
GT3語がASLの3区間に一対一で対応することを前提にせず、遷移・非手指動作・同時表現があり得るものとして扱う。
左右表記はモデルの解剖学的左右で、正面画像の画面左右と逆。口元へ上げる主な手は画面左／モデルright。

| GTの語・意味 | 意味に関係する可能性がある動作（未確認候補） | GTを予測する際のAttention | 予測側の参照・介入証拠 | 解釈・未確認点 |
|---|---|---|---|---|
| I／話者 | A：f12〜35、0.40〜1.20秒未満。片手を胸元へ上げ、指すように見える。f18〜30で明瞭 | 全層平均の重心2.033秒、中央80%0.367〜3.467秒。後段L9〜12のpeakはf24/14/20/24 | A固定で`▁say`のlog Pが−5.304。GT `▁I`は逆に+1.209 | 後段の胸元付近参照はあるが、Iの確定認識ではない。冒頭IのAttentionはIを入力後の値ではなく、decoder-startからIを予測する値 |
| want／要求 | B：f36〜61、1.20〜2.067秒未満。両掌を前に上げ、指を曲げながら下方・体側へ引くように見える | 重心2.148秒、中央80%0.367〜3.467秒。B質量16.99% | `heavy`のB質量37.95%、後段多数層でf42〜46がpeak。B固定で`heavy` log P−6.992 | 両手の動きがheavyの選択を支える証拠。wantとheavyの正しい語義対応・取り違え原因の確定ではない |
| water／水 | C：f62〜98、2.067〜3.30秒未満。片手を口元へ上げ複数指を伸ばした形で保持・小さく動かす。f66〜96で口元位置 | 重心2.243秒、中央80%0.633〜3.500秒。C質量34.59%、全層平均peak1.867秒 | `thirsty`のC質量48.63%、重心2.682秒。C固定で`thir` log P−2.108、GT `water` −0.522 | water関連動作からthirstyへ意味が近く誤った可能性は仮説。指形、接触、ASLとしての意味は人の確認が必要 |

窓幅はA24／B26／C37枚。一様分布なら質量は22.02%／23.85%／33.94%となる。
`heavy`のBは一様比1.59、`thirsty`のCは1.43だが、GT `water`のCは**1.02**にすぎない。
GT waterのAttentionが口元に強く集中しているとはいえない。
区間間のraw質量を窓幅を無視して比較しない。

全予測語について、単語Attentionを構成subwordの算術平均で集約した。
下表の重心・中央80%は映像位置だけで再正規化した分布、prompt質量は正規化前。
これは参照分布の要約であり、信頼区間・正解動作区間ではない。

| 実生成語 | peak秒 | 重心秒 | 中央80%の秒範囲 | prompt質量 |
|---|---:|---:|---|---:|
| They're | 1.867 | 2.174 | 0.467〜3.500 | 6.23% |
| going | 1.867 | 2.091 | 0.700〜3.467 | 2.88% |
| to | 1.867 | 2.375 | 0.800〜3.500 | 3.36% |
| say | 1.867 | 2.205 | 0.700〜3.467 | 2.83% |
| it's | 1.867 | 2.403 | 1.067〜3.500 | 2.32% |
| heavy | 1.867 | 2.241 | 1.133〜3.433 | 1.34% |
| or | 3.567 | 2.480 | 1.300〜3.467 | 2.99% |
| thirsty | 3.567 | 2.682 | 1.567〜3.500 | 1.92% |

複数語がf56＝1.867秒、f107＝3.567秒を共有する。
GTのIも平均peakはf107だが、層内head平均のpeakはL1〜7でf107、L8でf56、L9〜12で胸元付近に移る。
GT Iの144 layer/head重心は0.195〜3.148秒、中央値2.014秒と幅広い。
したがって平均だけから「Iを終了姿勢へ誤対応」と結論づけることもできない。

| 語 | peakがf56のlayer/head数 | peakがf107の数 | peak位置の種類数（144組内） |
|---|---:|---:|---:|
| They're | 53 | 27 | 35 |
| heavy | 39 | 14 | 41 |
| thirsty | 30 | 56 | 33 |
| GT I | 21 | 26 | 39 |
| GT want | 25 | 18 | 50 |
| GT water | 37 | 14 | 41 |

層・headは独立標本ではなく、上表から統計的有意差は計算していない。
文字列上の編集距離を映像対応に転用せず、語同士の強制的な整列も作成していない。

## 5. token、teacher forcing確率、EOS、文の長さ

予測の保存IDは先頭0を含む20個。診断対象はその後の19個。
単独`▁`は後続語へ、apostrophe・継続subwordは同じ語へ結合する。句点とEOSは独立行。
単語Attentionはtoken平均であり、長いsubword列ほど1語の重みを増やす集計ではない。

```text
They're: [259 ▁,10837 They,277 ',380 re]
going:   [259 ▁,5846 going]
to: [288 ▁to] / say: [3385 ▁say] / it's: [609 ▁it,277 ',263 s]
heavy: [259 ▁,39852 heavy] / or: [631 ▁or]
thirsty: [259 ▁,74283 thir,23734 sty] / .: [260 .] / EOS: [1 </s>]
GT: [336 ▁I,3007 ▁want,4582 ▁water,260 .,1 </s>]
```

teacher forcingではGT、または固定予測文をlabelsとして内部右shiftし、各tokenの条件付きlog Pを取得した。
**GTを与えてAttentionを得たことは、自由生成で正解を出せたことを意味しない。**
同じ時刻位置でも予測とGTで先行文が異なるため、Attention・確率の語間比較は同条件の比較ではない。
第1decoder入力だけは共通の`<pad>`で、GT先頭AttentionにはまだIの情報は入力されていない。
条件が共通でも、一括計算する系列長19対5によるBF16の数値差は残る。
例えば単独`▁`の冒頭確率は予測TFで0.111413、GT TFで0.108441となるため、以下の冒頭候補比較はGT側の同一logit行内で行った。

| GT target（直前までのGTを入力） | 確率 | 自然対数確率 | vocab内順位 |
|---|---:|---:|---:|
| ▁I | 0.015142 | −4.1903 | 8 |
| ▁want | 0.017083 | −4.0697 | 11 |
| ▁water | 0.000200 | −8.5184 | 41 |
| . | 0.004886 | −5.3213 | 16 |
| EOS | 0.789081 | −0.2369 | 1 |

同一のGT先頭logit行で `P(単独▁)=0.108441`、`P(▁I)=0.015142`（7.16倍の差）。
この単独空白token自体はThey'reという語に限定されない。
`I want`の後は `to`23.32%、`it`17.06%、単独`▁`8.58%、`you`8.06%、`the`5.54%がtop5。
正しい短い要求文を促すGT prefix下でもwaterの選択は弱い。

| 固定文 | EOS込みtoken数 | log P合計 | token平均log P | EOS除外のtoken平均log P |
|---|---:|---:|---:|---:|
| 元予測 | 19 | −16.6589 | −0.8768 | −0.9138 |
| GT | 5 | −22.3366 | −4.4673 | −5.5249 |

合計はtoken数と分割方法に依存し、平均も翻訳正確性・長さに中立な尺度ではない。
モデル内部でこの予測経路の条件付きスコアが高いことを示すだけで、翻訳信頼度ではない。
介入では同じ固定文・同じtoken位置間の差を使う。

元予測prefixに対するEOS確率は、句点を予測する手前まで最大でも **0.00001936（0.001936%）**。
`thirsty`まで入力した段階では句点78.99%、EOS0.0151%。句点入力後にEOSは81.03%になる。
GTでも `I want water` の後の句点は0.4886%、`to`20.14%が優先され、EOSは約0.0042%。
しかしGTの句点まで強制するとEOSは78.91%になる。
終端tokenを出せない障害ではなく、語の選択と句点に至るまでの続きをモデルが優先する挙動が見える。

生成設定だけを変えた対照も実行した。

| 設定 | 自由生成 |
|---|---|
| 元：beam4／length_penalty1 | They're going to say it's heavy or thirsty. |
| beam4／length_penalty0 | They're going to say it's heavy or heavy. |
| greedy（beam1） | They're going to say that it's heavy or heavy. |

length penaltyとbeam探索は末尾選択に影響するが、0にしても3語の要求文には戻らない。
max_new_tokens100への到達で終了した結果でもない（元予測はEOS込み19token）。
以上はEOSの確率、生成上限、探索設定の寄与を部分的に切り分ける結果である。

## 6. 入力介入：Attentionと因果的な依存の区別

元poseを一度正規化してから介入し、正規化scaleの全体変動を避けた。
時間窓は全4部位の座標とscoreを窓直前フレームで置換。
static_middleはf54で全系列を固定、reverseは全系列逆順。
left/right_staticはその手の局所座標・scoreだけをf0で固定し、body経由の手首位置は残す。
これらを「手の全情報除去」とは呼ばない。
全条件で117位置を維持。prefix_only以外はattention maskも完全一致させた。

表のΔは**EOS込み平均log Pの介入後−元**。負は同じ固定文が出にくくなったことを表す。
各行で自由生成と両固定文の全token確率を実測した。

| 介入 | 自由生成 | Δ予測 | ΔGT |
|---|---|---:|---:|
| 全系列f54で静止 | The next thing I'm going to do is I'm going to show you a little bit of how to do the ice fishing. | −1.1296 | −0.0899 |
| 逆順 | JOE PARSONS: You're going to want to make sure that you're telling your wife. | −0.3992 | +0.1614 |
| left局所手形をf0で固定 | They say there's already a straw in there. | −0.3265 | −0.0201 |
| right局所手形をf0で固定 | So you're going to take a piece of clay, and you're going to take a piece of clay, and you're going to take a piece of clay. | −1.5968 | −0.6950 |
| A：f12〜35固定 | You want to make sure that you're not getting too heavy or too heavy. | −0.4898 | +0.6382 |
| B：f36〜61固定 | They're going to say, well let's say it's true. | −0.5868 | +0.0495 |
| C：f62〜98固定 | They're going to be a little bit shorter, but they're going to be a little bit shorter. | −0.3582 | −0.2105 |
| peak付近f52〜61固定 | They're going to say that it's heavy or heavy. | −0.0321 | −0.0797 |
| 末尾f99〜108固定 | They're going to say that it's heavy or really heavy. | −0.1085 | +0.1329 |
| encoder前の映像109埋め込みを0 | It's very important that you're going to be lifting and lifting. | −1.5882 | −0.4061 |
| 映像埋め込み0＋映像mask0 | O.k. | −1.2203 | +0.6040 |

最後の条件のみmaskを変え、学習済み翻訳モデルに固定prefixだけを有効入力として与える。
元の事前学習mT5の純粋な言語モデル比較ではない。
ゼロ映像条件は映像内容を除いても位置数・maskを残すため、完全な無条件生成ではない。
静止化やゼロ化は自然なASLから外れる。窓長・変化量が違うため、Δの大小をそのまま原因の割合に換算しない。

主要なtoken差は次のとおり。

| 固定されたprefixで予測するtoken | 介入 | Δlog P | 解釈 |
|---|---|---:|---|
| heavy | B全体 | −6.992 | 同じ文章prefixでも両手区間がheavyの確率を支える |
| heavy | B内のf52〜61だけ | −0.103 | 平均Attentionが最大のf56付近だけを変えた効果はB全体より小さい |
| thir（thirstyの開始subword） | C全体 | −2.108 | 口元区間はthirstyの確率を支える |
| thir | 末尾f99〜108 | −0.650 | 末尾ピークにも感度はあるが、終了姿勢がthirstyを意味する証明ではない |
| heavy / thir | right局所手形固定 | −6.000 / −6.166 | 主に動く側の局所手形系列へ依存 |
| GT water | right局所手形固定 | −1.883 | 正解候補waterにも同枝由来の支持があるが、元の絶対確率は非常に低い |
| GT I | A固定 | +1.209 | 胸元候補を保てば必ずI確率が高いという単純対応を支持しない |

f52〜61とf99〜108の追加介入は、初回解析で全層平均peakがf56／f107に集中した観察を受けて選んだ。
f56は「全語にとって最重要な実演フレーム」とは解釈できず、Attentionの強さと置換効果の差が実際にある。
ただし静止置換はその位置を削除する操作ではなく、情報の冗長性・置換前後の類似性・encoder混合もある。
この結果だけでAttentionを無意味としたり、f56を原因から除外したりはできない。

## 7. どの段階に問題を示す証拠があるか

### 観測事実

- **取得・時間順序**：入力、pose、選択番号、フレーム数、生成IDが整合。時間間引き、順序取り違え、mask欠落を示す証拠は見つからなかった。
- **姿勢抽出**：使用69点の低score maskは保存記録で0%、今回の正規化系列も有効。overlayは大きな手首・腕移動を追う。一方、胸・口元では指が重なり、骨格指先の位置と実指形の一致を画像だけで確定できない。高scoreは指形の正確さを保証しない。
- **時系列特徴**：空間・時間ST-GCNの各部位出力、pose投影、全encoder／decoder層のhidden statesを取得した。pose投影の隣接cosine平均0.958、encoder最終層0.964。全非対角cosine平均は0.462→0.200で、全位置が同じ特徴に崩壊した結果ではない。
- **encoder混合**：映像queryからj±6外の映像keyへのAttention質量は層・head・query平均でL1=32.26%、L12=68.97%。遠方文脈を参照している。ただしこれも因果寄与率ではない。
- **特徴から語の選択**：B区間とright局所手形を変えるとheavy等の固定prefix確率が大きく変わる。元の誤文は映像特徴と無関係に出ているわけではない。
- **文章生成**：GT prefix下でもwaterや短文終端の句点が低確率。語選択と文の続きの段階に明確な不一致がある。beamやlength penaltyの変更だけでは解消しなかった。

### 証拠と整合する仮説

1. 両手の動きからheavy、口元の動きからthirstyという関連するが誤った語義へ写像され、説明調の先行文がそれを文にしている可能性。区間介入は依存を支持するが、どの層が意味を取り違えたかは未確定。
2. How2Signで学習した視覚・文章分布とこの短い自前要求文の差が影響している可能性。静止・ゼロ特徴で説明調の長文が出ること、`I want`の後に`to`が優先されることと整合する。学習コーパス頻度を実測した結論ではない。
3. 口元や胸元の細かな指形のpose誤差が視覚表現を曖昧にする可能性。pose修正・別抽出器との同条件比較をしていないため、原因と断定できない。

### まだ分からないこと

- I／want／waterに対応するASLとしての正確な意味区間と境界。実演者またはASL確認者による指形・動作・非手指表現の確認が必要。
- 正しい手形poseを与えた場合の翻訳。今回は保存poseを固定したため、抽出器の正確性そのものは検証していない。
- 部位特徴・pose_proj・mT5 encoderのどこで意味情報が不足／変換されたか。hidden statesの変化だけでは意味の正誤を判定できない。正解pose・比較動画・意味ラベル付きprobeなしに局在を断定しない。
- 文章側だけの寄与率。prefix-only、zero-embeddingは分布外対照であり、decoderの事前傾向を自然入力下で完全に切り離したものではない。
- 他話者・他文・他手話動画で同じ傾向が再現するか。この1本からモデル全般の精度や優劣を結論づけない。

## 8. 再実行方法・機械可読データ

自作コードは[解析](../scripts/analyze_temporal_attention.py)と[可視化](../scripts/visualize_temporal_attention.py)。
プロジェクトルートで専用環境を使用する。`--output-dir`は未作成の名前を指定する。
以下の`r3`は実際に実行したコマンド。再実行時は例として`r4`へ変更する。

```bash
/home/kosaki/anaconda3/envs/Uni-Sign/bin/python -B \
  research/sign/uni-sign/scripts/analyze_temporal_attention.py \
  --result research/sign/uni-sign/Uni-Sign/outputs/20260912-self-03-06-preprocessed-evaluation-r1/06_i_want_water_vertical/crop_pad_resize/result.json \
  --output-dir research/sign/uni-sign/Uni-Sign/outputs/20260912-water-attention-r3

/home/kosaki/anaconda3/envs/Uni-Sign/bin/python -B \
  research/sign/uni-sign/scripts/visualize_temporal_attention.py \
  --analysis-dir research/sign/uni-sign/Uni-Sign/outputs/20260912-water-attention-r3 \
  --result research/sign/uni-sign/Uni-Sign/outputs/20260912-self-03-06-preprocessed-evaluation-r1/06_i_want_water_vertical/crop_pad_resize/result.json \
  --overlay research/sign/uni-sign/Uni-Sign/outputs/20260912-self-03-06-preprocessed-pose-overlays-r1/06_i_want_water_vertical/crop_pad_resize/pose_overlay.mp4
```

解析スクリプトは専用Pythonの場所をハードコードせず、起動した`sys.executable`を子プロセスにも使用する。
別環境では同じ依存条件のPythonへコマンド先頭を変更する。
上流cwd・offline環境変数・ライブラリ探索パスをlauncherが設定する。
worker用内部引数を直接呼ばず通常launcherから実行する。可視化も新規figuresのみ作成する。

| ファイル | 内容 |
|---|---|
| `manifest.json`、`environment.txt`、`command.txt`、`analysis.log` | 入力条件・重み／コード／tokenizer hash、revision、環境、実コマンド、ログ |
| `integrity.json`、`visualization_manifest.json` | 入力整合性、overlay hash、可視化コードhash |
| `summary.json` | 再現検証、完全な生成設定、baselineと全介入のtoken別確率、自由生成、探索対照 |
| `generation_attention.npz` | 実生成最終beamのcross `[12,12,19,117]`、encoder attention、beam祖先、transition log P |
| `prediction_teacher_forced.npz`、`gt_teacher_forced.npz` | cross、encoder／decoder self-attention、全層hidden states。GT crossは`[12,12,5,117]` |
| `intermediate_features.npz`、`normalized_pose.npz` | 部位別空間／時間GCN、pose_proj、mT5入力、正規化pose。共有hand moduleの呼出し0=left、1=right |
| `prediction_tokens.json`、`gt_tokens.json`、`token_probabilities.csv` | token ID、subword、prefix、確率／log確率、EOS確率、順位。JSONにはtop5も保存 |
| `word_mapping.json`、`time_mapping.json` | subword→語、encoder位置→フレーム／秒／受容野、集約定義 |
| `attention_time_statistics.csv`、`layer_statistics.csv`、`layer_head_statistics.csv` | token／語のpeak、重心、quantile、区間質量、層／head変動 |
| `interventions.csv`、`intervention_token_probabilities.csv` | 同一固定文の介入前後差、全自由生成、tokenごとの差 |
| `observations.json`、`feature_statistics.json` | 未確認の動作観察区間、特徴の類似度／encoder混合等 |
| `analysis_script.py.txt`、`visualization_script.py.txt` | 最終実行時のスクリプトのコピー。Git対象外の再現用snapshot |

`r1`は通常sandboxからCUDAに接続できずモデルロード前に失敗したログ。
GPUアクセス可能な実行に切り替えた`r2`で主要解析を完了し、peak付近の追加2介入と実行コード保存を加えた`r3`を最終成果物とした。
いずれも元の評価成果物を上書きしていない。
TensorFlowのCUDA11ライブラリに関するimport時warningはログにあるが、この推論はPyTorch CUDA12.1で完了した。
未取得の内部量を代用値として記載していない。全headのcross/self-attentionと中間特徴は取得できたが、ASLの意味ラベル付き内部量はモデルから提供されない。

コード経路・既存記録・時間受容野・解析式の独立レビューをsub-agentがCPU読取のみで担当し、
主エージェントがGPU実行・入力画像の目視・図・報告を統合した。
最終成果物への動画・骨格・重みのGit追加、外部サービスへのデータ送信は行っていない。
最終確認では全NPZの有限性、cross-attentionの形状と行和、全11介入の固定token列一致、
実行scriptのSHAと現コードの一致、Python構文、全レポートリンクの存在を検証した。図は14枚。
このワークスペースでは`git status`は有効なGitリポジトリでないため実行できなかったが、
既存`.gitignore`のUni-Sign checkout／outputs／動画／骨格の除外規則を確認し、stage・commitは行っていない。

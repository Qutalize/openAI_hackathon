# Uni-Sign / How2Sign：自前ASL動画の翻訳不一致調査

2026-09-12。主エージェントがGPU診断と統合、Aがコード・重み、Bが入力・前処理、CがWeb一次資料を独立調査した。各担当の結論を相互照合した。

## 結論と入力情報の更新

**英文生成は成功しているが、正しいASL→英文翻訳は2本とも確認できなかった。単一の根本原因は確定していない。**

調査中、ユーザーが入力言語をASL、各動画と同じディレクトリの `script.txt` を正解ラベルと確認した。この確認を最終評価の前提とする。初回報告・入力READMEにある「言語・原稿未確認」は調査開始時点の情報であり、今回の最新情報とは異なる。`02` の実ファイルは挨拶と体調を尋ねる2文で、初回に引用された暫定原稿より具体的だった。原稿ファイルは評価時にだけ読み、推論に渡していない。元動画・原稿・過去の結果は編集していない。

確認できた問題は、**有意味な姿勢情報を失った人工入力でも英文を生成することと、演算精度・姿勢抽出条件の違いで生成文が変わること**。ただし後者を変えても正解には改善しなかった。原因候補として、How2Signの学習分布との違い、学習用とデモ用の姿勢抽出器の違い、個々の指形・動きの復元誤差が残る。

「入力がASLではない」はユーザー確認後の主要仮説から外す。一方、個々のASL表現・指形・区間境界が正解ラベルを十分に伝えているかを、独立した熟練者が検証したわけではない。

## 確認済みの問題と原因候補

| 仮説 | 根拠・実施した検証 | 結果と判断 |
|---|---|---|
| 姿勢が意味を伝えなくても生成器が英文を出す | 正規化済みの全4部位をゼロ化。系列長・attention mask・固定言語prefixは保持 | 両入力長で同じ手順説明文を生成。異常な姿勢を拒否する動作は確認できない。今回の誤訳がこの性質によるとまでは単独で証明しない |
| 数値精度への感度 | 同じ保存pose・元checkpointを読み、BF16/FP32演算を比較。各条件を同一プロセスで反復 | `01` の文が変化。固定条件の反復はtoken列まで同一。どちらも正解と無関係で、FP32化は対処にならなかった |
| 抽出の実行条件への感度 | 同じONNXを16-threadと逐次で実行し、保存poseの座標・score・生成を比較 | poseに差あり。BF16では両動画の生成が一致したが、FP32では `02` の文が変化。スレッド競合や特定バグが原因と断定する検証ではない |
| How2Signの学習分布との違い | 公式論文・データセット資料を照合 | 手順説明中心のstudio ASLと、自前の短い対人的な挨拶・質問では話題・撮影・表現者が異なる。手順説明風の誤出力と整合する有力候補。短さだけが原因という根拠はない |
| 学習用と公開デモの姿勢抽出器の違い | 上流作者のIssue 20回答とローカル設定を照合 | 処理系の違い自体は確認済み。今回の不一致への寄与は未測定。元抽出器との比較は新規重み・環境が必要になり得るため未実施 |
| 手指の抽出品質 | 骨格重ね表示、全部位のscore・ゼロ化率を計測 | ブレ・重なり・一部の指先追従に疑問が残る。ただし手の低scoreは主に安静時・画外に集中し、「動作中の大量欠落」を主因にする根拠はない |
| 鏡像・表現の適合性 | メタデータ・映像・ユーザー説明 | 正立。ユーザーの左手が画像右側に映る説明は非反転の正面像と整合。鏡像設定は未確認だが、反転を追加する根拠はない。ASL技能・表現の正確さは独立評価していない |

How2Signは手順説明動画をASL化した約80時間、11名、studio収録のデータセット。公開クリップには英語字幕とASLの時刻のずれがあり、手動再整列版が別途提供される。これは今後の公式サンプル比較で揃える条件であり、自前動画の不一致原因をラベル品質へ帰す証拠ではない。[How2Sign論文](https://arxiv.org/pdf/2008.08143)、[公式資料](https://how2sign.github.io/)

Uni-SignはASL側でYouTube-ASLによる事前学習後、下流データセット別に学習する。How2Sign pose-onlyの論文Test BLEU4は14.5であり、自前動画の精度・成功確率ではない。短文の翻訳例もあるため、「短いから翻訳不能」とは判断しない。[Uni-Sign論文 §4](https://arxiv.org/html/2501.15187v3#S4)

作者は元のMMPose抽出から公開デモのRTMLibへ変更し、keypointと推論文が変わり得ると説明している。元構成はRTMDet-mとRTMW-x、今回の軽量デモはYOLOX-tinyとRTMW-l。作者の「全体性能には大差ないはず」は見解であり、今回の保証ではない。Issueの実例はCSLで、ASLの本動画に対する直接実験ではない。[Issue 20の説明](https://github.com/ZechengLi19/Uni-Sign/issues/20#issuecomment-3242920526)、[元構成](https://github.com/ZechengLi19/Uni-Sign/issues/20#issuecomment-3434904141)

## コード・モデル整合性：否定できた候補と残る限界

行番号の起点は `research/sign/uni-sign/Uni-Sign/`、revisionは `eed438bcb49e30405cd6ccdfcccca330c134e830`。

- `models.py`、`datasets.py`、`demo/online_inference.py` にローカル差分なし。既知のパッチはmT5パス、推論時のDeepSpeed import回避、ORT provider表示・失敗検出。認識ロジックの改変を原因とする根拠はない。
- `models.py:104,140,269`：How2SignでEnglishを選び、ローカルmT5 tokenizerと固定の英語翻訳prefixを使用。`datasets.py:625` の空targetは `models.py:282` 以降の余分なloss計算にだけ使用し、`:313` のgenerateはembeddingとmaskを参照する。原稿漏洩・空文promptによる誤訳ではない。
- `demo/online_inference.py:51,59,60,114`：strictロード、eval、BF16、no_grad。初期の `model.train()` は推論前に解除される。`:125` のbeam 4 / max_new_tokens 100は `fine_tuning.py:263` の評価と整合。サンプリング・forced token・語彙制約なし。
- checkpointのSHA256は `1bfd5f3312f04e4736f0a52f4ef9535916e6de9676a2a0d00c708748683fb00d`。既知の公式一致値を再確認。627 state keys（BF16 583、int64 44）、全浮動tensorはfinite。mT5の284キーを含み、共通embeddingと左右共有層85組も一致。重み欠落・NaN/Inf・共有aliasの矛盾は検出されなかった。
- **strictはキーと形状を確認するだけ**で、学習時tokenizerとの完全一致、非tensor設定、正しい姿勢や翻訳品質を保証しない。checkpointは `model` のみで学習設定metadataがない。mT5は既録の固定revision由来だが、学習時ファイルとの直接照合はできない。
- `tokenizer_config.json` 内の `google/mt5-small` という文字列は公式mt5-base配布にもあるため、誤モデル取得の証拠ではない。[公式固定revisionの設定](https://huggingface.co/google/mt5-base/blob/2eb15465c5dd7f72a8f7984306ad05ebc3dd1e1f/tokenizer_config.json)
- `config.py:43` のHow2Sign offline pose_dirが別データを指す点は、今回の `pose_data` 直接入力では参照されない。Decordのpip checkメタデータエラーも残るが、pose-only経路の動画取得はOpenCVで成功している。
- 既存の2生成文を同梱How2Sign train 31,086文・test 2,349文と比較し、小文字化・句読点除去後の完全一致は0件。「特定学習文の丸写し」は確認できない。類似文検索の値は翻訳精度ではない。

両動画の報告フレーム数とデコード件数の不一致、256上限による間引き、幅高さの逆転、133点の手index不整合、出力言語の取り違え、今回の逐次抽出での人物未検出fallbackは否定できた範囲に含む。撮影時のフレーム落ちや不均一な時刻間隔は未測定。GPU実行成功自体は意味認識成功を保証しない。

## 入力・骨格の実測

OpenCVで1920×1080、約30fps、121 / 155フレームを取得。正立・正面の1名を各12フレームで目視。全フレームの逐次detector box数とpose人数は1、座標・score・正規化入力はfiniteだった。

| 入力ID | bodyのmask率 | 左手のmask率 | 右手のmask率 | 選択顔点のmask率 |
|---|---:|---:|---:|---:|
| `01_whats_your_name` | 0.55% | 4.21% | 13.62% | 0% |
| `02_greetings` | 0% | 5.44% | 4.76% | 0% |

mask率は全フレーム×各部位点のscore≤0.3の比率。左右はCOCOの身体側で、表示画像の左右ではない。scoreはSimCC出力に由来し、1を超える値もあり、校正済み確率や翻訳信頼度ではない。`datasets.py:19,68-71,102-104` に従い該当点のx,y,scoreをすべて0にする。

`01` のframe36–118、`02` のframe8–153では両手のmask率は0。全体の欠落率は主に安静時・画外の手を反映する。高scoreでも正しい指形の保証はなく、01のframe10/32、02のframe112/126/140などのブレ・曲げた指先は追加確認箇所。全身骨格の崩壊や明白な左右入替えは見えなかった。

onlineと通常datasetは `load_part_kp` を共有（`datasets.py:461-497,634-665`）。体幹9点、各手21点、顔18点を使用し、全時系列のbody scale、手首相対、顔53番相対で正規化する。COCO133に対する手の91:112 / 112:133は整合。画像を直接翻訳モデルへ戻すRGB補助は使っていない。姿勢モデル入力は192×256なので、原動画HDの指形情報をそのまま使えるわけではない。

並列と逐次の座標差は、多くの有効点で小さい一方、局所的な大きな差もあった。両方score>0.3の手点に限定した最大差は01左手0.097、02左手0.121（幅/高さ正規化座標）。99パーセンタイルは両動画の手で約0.0033～0.0036。閾値をまたぐ手点は各動画6個。全133点の最大差0.63 / 1.14は未使用点・低score点も含み、それだけを翻訳入力の破綻の証拠にしない。

## GPU対照実験の結果

専用conda環境、既存ONNX・How2Sign重み・mT5を使用。GPU実行は主のみで順番に行い、新規依存・checkpoint取得なし。両runはexit code 0。終了後GPUは21MiB、利用率0%に戻った。

1. `r1`：上流16-threadでposeを再抽出し、逐次抽出と比較・可視化。同じ正規化poseでBF16 baseline、repeat、reverse、static_middle、zero、およびFP32 baselineを生成（2本×6条件=12出力）。
2. `r2`：r1の並列/逐次poseを固定し、BF16/FP32で各baseline/repeatを生成（2本×2抽出×2精度×2反復=16出力）。

| 条件 | `01` | `02` | 意味の正しさ |
|---|---|---|---|
| r1/r2 BF16、並列pose | 元の生成とは異なる保持時間の説明文。固定条件の反復と別プロセスのr2は一致 | 元と同じカードに関する文 | 両方不一致 |
| r2 BF16、逐次pose | 並列poseのBF16と同じ | 並列poseのBF16と同じ | 両方不一致 |
| r1/r2 FP32、並列pose | 元と同じ器具・重さに関する文 | 元と同じカードに関する文 | 両方不一致 |
| r2 FP32、逐次pose | 並列poseのFP32と同じ | 並列poseと異なる大きさ等の描写文 | 両方不一致 |
| BF16 reverse | baselineと異なる手順説明文 | baselineと異なる手順説明文 | 時系列には反応するが正解ではない |
| BF16 static_middle | 向きに関する反復的な説明文 | 紙の量に関する反復的な説明文 | 有意味な連続手話の対照ではない |
| BF16 zero | 両動画長で同じ調理手順の説明文 | 左と同じ | 有意味な姿勢情報がなくても生成 |

生英文・token列はローカル `results.json`、確認済み正解との照合は `r2/evaluation.json` に保存。28出力に正規化完全一致はなかったが、人工負例・重複反復を含む28件を独立した翻訳精度評価の母数にしない。原文を持つ入力は2本だけ。

FP32は演算精度だけの比較。配布checkpoint自体がBF16であり、保存前の精度は復元しない。上流onlineは `--dtype` と無関係にBF16へ固定するため、診断コードで明示変換し各精度で元stateを再ロードした。

reverse/static/zeroは**正規化後**の人工対照。zeroは真っ黒動画そのものではなく、系列長・mask・prefixは残るので「完全に無条件の生成」とは呼ばない。逆順で文が変わることも、正しいASLの意味を読めた証明ではない。初回とr1は元poseを共有していないため、初回からの出力変化をBF16だけに帰すことはできない。

## 学習なしでできる対処と次の検証

1. **正解が確定したASLの対照1本で、翻訳系と自前入力を切り分ける。** 公開・使用可能なHow2Signの文区間、対応ラベル、可能なら配布poseを同じサンプルで揃え、配布poseと自前抽出poseを比較する。必要なサンプル/poseは今回未取得。大量データを先に取らない。
2. 自前2本はASLに習熟した人に個々の表現・区間境界を確認してもらう。必要なら同じ内容を、顔と動作中の両手を画内に保ち、指先のブレが少ない条件で再撮影する。正解への一致を見ながら恣意的にcrop・鏡像・語彙を調整しない。
3. 前処理比較は保存poseを固定する。現時点でFP32化や逐次抽出は正しく翻訳する対処になっていない。元MMPose/RTMW-x構成との比較は意味があるが、必要重み・容量・追加環境への影響を確認して承認を得てから行う。現在の環境へ独立に追加しない。
4. **OpenASL pose-onlyを同一入力・同一pose・同一生成設定で比較する。** 別のASL学習分布への感度を見られるが、成功保証ではない。OpenASLは288時間・200名超、ニュースやvlogを含む。原論文は定型句の重複/非重複で一般化性能が異なることも報告しており、その分析をUni-Sign自身の実測と混同しない。[OpenASL論文](https://aclanthology.org/2022.emnlp-main.427.pdf)

OpenASL重みは1,186,924,838 bytes（約1.19 GB、1.11 GiB）、SHA256 `f836ea66bc837bbe6ed717a4b9bece87875f03ef96d4bf1092ca3dd767982798`。公開pointerの確認のみで本体は取得していない。取得するなら別ファイルを追加し既存mT5を共有する想定だが、実ロードの互換性は未検証。新規checkpointなので実行前の承認対象。[配布ページ](https://huggingface.co/ZechengLi19/Uni-Sign/blob/main/openasl_pose_only_slt.pth)

現在の結果から、学習なしで正しい自前ASL翻訳を保証できる対処は見つかっていない。既存モデル選択・確認された前処理問題の修正・撮影改善の範囲で検証を進める。LLM補正、正解prompt、学習・fine-tuningは行わない。両モデルが失敗しても非ASLの証明にはならず、期待文に近くても表現の独立確認の代用にはならない。

## 再現コマンド・変更・保存先

作業ディレクトリはプロジェクトルート。以下は実行済み。再実行時は新規 `--output-dir` に変える。既存保存先は上書きを拒否する。

```bash
conda run --no-capture-output -n Uni-Sign python -B \
  research/sign/uni-sign/scripts/diagnose_online.py \
  data/sign/01_whats_your_name/original.mp4 \
  data/sign/02_greetings/original.mp4 \
  --output-dir research/sign/uni-sign/Uni-Sign/outputs/20260912-mismatch-diagnostic-r1

conda run --no-capture-output -n Uni-Sign python -B \
  research/sign/uni-sign/scripts/diagnose_online.py \
  data/sign/01_whats_your_name/original.mp4 \
  data/sign/02_greetings/original.mp4 \
  --cached-poses research/sign/uni-sign/Uni-Sign/outputs/20260912-mismatch-diagnostic-r1 \
  --output-dir research/sign/uni-sign/Uni-Sign/outputs/20260912-mismatch-cached-r2
```

| 配置（`research/sign/uni-sign/` 起点） | 内容 |
|---|---|
| `scripts/diagnose_online.py` | 新規。既存上流コードを呼ぶ姿勢診断・対照生成。原稿は読まない |
| `reports/2026-09-12-how2sign-mismatch-investigation.md` | この統合記録 |
| `README.md` | 最新のユーザー確認と調査記録へのリンクを更新 |
| `Uni-Sign/outputs/20260912-mismatch-diagnostic-r1/` | manifest、コマンド、依存一覧、GPUログ、結果JSON、2方式のpose NPZ、骨格contact sheet、追加座標比較JSON |
| `Uni-Sign/outputs/20260912-mismatch-cached-r2/` | 固定poseの追加比較、生英文・token、評価JSONと評価用 `summarize.py` |
| `Uni-Sign/outputs/20260912-code-audit-a1/` | AのCPU診断script・JSON・根拠行番号付き記録 |
| `Uni-Sign/outputs/20260912-input-audit-b1/` | BのCPU映像診断script・メタデータ・contact sheet・骨格照合記録 |
| `Uni-Sign/outputs/20260912-source-audit-c1/` | Cの一次資料記録・URL・再現コマンド |

診断生成物は既存Uni-Sign/outputsの下の新規ディレクトリのみ。映像・顔画像・ランドマークは外部送信しておらず、Git対象外。上流・依存・重みを変更せず、既存のpycache差分も復元しなかった。共有ルートは有効なGit repositoryとして認識されないためstage/commitは実施していない。

検証は実GPUでの2run、CPU checkpoint監査、保存結果のfinite/反復/正解一致照合、診断scriptの構文確認、Aによる対照実装レビュー、Bによる骨格再確認。入力・重みの識別値はmanifestに保存。翻訳信頼度は今回も未提供で、姿勢scoreを代用しない。

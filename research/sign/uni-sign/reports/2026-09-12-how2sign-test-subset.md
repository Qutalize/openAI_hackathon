# Uni-Sign / How2Sign：評価データ12組での配布pose・動画推論の比較

2026-09-12。目的は、自前ASL動画の翻訳不一致について、評価データでも動かない推論系の問題か、自前入力との適合性やモデル性能の限界かを切り分けること。学習・fine-tuning・LLM補正なし。

## 結論

**評価用How2Signでも一部の意味は翻訳できたが、誤訳が多く、安定して正しく翻訳できる状態ではない。自前動画だけを不一致の原因とはできない。**

上流のtestラベル2,349件から、出力を見る前にseed42で12件を固定した。作者配布poseと対応動画をダウンロードし、同じモデル・同じ選択フレームで比較した。

| 入力からの経路 | 実行成功 | BLEU-1 | BLEU-2 | BLEU-3 | BLEU-4 | ROUGE-L | 文字列完全一致 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 作者配布pose → モデル | 12/12 | 35.53 | 24.67 | 19.00 | **14.96** | 29.98 | 0/12 |
| 同じ動画 → 公開デモのpose抽出 → 同じモデル | 12/12 | 35.53 | 23.65 | 17.33 | **12.83** | 29.64 | 0/12 |

論文のHow2Sign pose-only全test値はBLEU-4 **14.5**、ROUGE **34.3**。今回の配布poseの値は同程度の数値だが、12件・batch1の診断なので全test再現や統計的な同等性を証明しない。BLEUは正答率ではなく、完全一致0件も意味一致0件を意味しない。[Uni-Sign論文 Table 6 / 21](https://arxiv.org/html/2501.15187v3#S4)

分かったことは次の3点。

1. **推論系は評価分布で部分的な翻訳能力を示す。** 学習済みcheckpoint・tokenizer・生成処理が全面的に取り違わされているという疑いを弱める。ただしコードの完全な正しさを証明するものではない。
2. **公開デモの抽出器だけでは不一致の全体を説明できない。** 配布poseを直接入れても対象物の置換・省略・反復が起きる。再抽出によるBLEU-4低下はこの12件で2.12ポイントだが、全データや自前入力での影響の大きさは未確認。
3. **モデルの翻訳性能の限界と、自前入力の話題・表現・画角との違いが残る。** 「ベンチマークでは常に正確で、自前だけ失敗する」という結果ではなかった。今回だけで自前動画の表現や撮影を誤りと断定できない。

## データセットと取得元

使用モデルは既存の `weights/how2sign_pose_only_slt.pth`。対象はASL→英文、評価データは**How2Sign test**。CSL-Daily用の評価例やOpenASLの重みへ切り替えていない。

- [How2Sign公式](https://how2sign.github.io/)：手順説明を中心としたASLのデータセット。原時刻による文分割と、手動再整列の時刻情報を区別する。
- [公式CORA配布](https://dataverse.csuc.cat/dataset.xhtml?persistentId=doi:10.34810/data33)：original / realigned test CSVを取得。各2357行、公式MD5と保存ファイルが一致。CSV転送コマンドはTLS EOFでexit56だったが、全bytesとMD5の一致で内容を検証した。
- [Uni-Signのデータ準備資料](https://github.com/ZechengLi19/Uni-Sign/blob/eed438bcb49e30405cd6ccdfcccca330c134e830/docs/DATASET.md)：作者配布のMMPose/RTMPose姿勢データを指定。
- [作者配布の固定revision](https://huggingface.co/ZechengLi19/Uni-Sign/tree/eab251b7fe7e8521afc0e67be98add670ea40a0d)：今回取得した `how2sign_pose_format.zip.00–03` と `how2sign_rgb_format.zip.aa–ae` の出所。

上流の `data/How2Sign/labels.test` はgzip圧縮pickleの2,349件。全件について公式CSVにIDがあり、英文が完全一致した。公式CSVにだけ存在する8件の除外理由は未確認だが、今回の選択12件はすべて共通部分にある。利用条件は公式の研究用途・CC BY-NC 4.0の記載を確認し、ローカル検証に使用。再配布していない。

ZIP全体はpose **8,465,474,575 bytes**、RGB **20,190,769,371 bytes**。HTTP RangeでZIP索引と対象ファイルの圧縮ブロックだけを取得したため、合計転送は **43,750,634 bytes（約43.8MB）**、保存された12組の動画＋poseは **11,179,188 bytes（約11.2MB）**。ZIP展開時のCRC32検査を通し、各ファイルのSHA256をmanifestに記録・再照合した。全shardは取得していないため、全shardのLFS SHA256をローカル計算したとは扱わない。

## 選択と区間の対応

選択は `random.Random(42).sample(list(labels.test), 12)`。元ラベル辞書の順序を保持し、意味・長さ・予測の良さで選び直していない。11の元動画からの12区間で、1つの元動画から2区間を含む。

| 順番 | test ID（末尾 `-rgb_front.mp4` を省略） | pose/動画フレーム数 | 使用フレーム数 |
|---:|---|---:|---:|
| 0 | `G19uBylwQww_0-2` | 196 | 196 |
| 1 | `92V3oH63zbQ_7-1` | 180 | 180 |
| 2 | `G3k86AVFwVs_10-5` | 194 | 194 |
| 3 | `G3RvsnzQrXQ_7-10` | 204 | 204 |
| 4 | `G3FhmHz_7hs_19-5` | 281 | 256 |
| 5 | `G21Gx_C18IA_4-2` | 287 | 256 |
| 6 | `G0Q6AlvH96I_15-2` | 269 | 256 |
| 7 | `g3X3XE6M2_A_15-3` | 44 | 44 |
| 8 | `G095RWKQ39g_19-1` | 71 | 71 |
| 9 | `g0iNy-yPisM_17-8` | 56 | 56 |
| 10 | `FZCF7kPIyOk_18-1` | 146 | 146 |
| 11 | `FZCF7kPIyOk_10-1` | 35 | 35 |

CPU独立確認で、12/12組について**配布pose長＝動画の全フレーム実デコード数＝動画metadata件数**。配布poseの `w_h` と動画寸法も一致した。poseにstart/endはなく、二重の時刻切り出しは不要。

24fpsまたは30fpsで、動画区間長は公式realigned CSVと最大2.24フレームの差。一方original CSVとは最大166.3フレームの差があった。手動再整列版との整合を支持する。元のfull videoを取得していないため、絶対開始時刻までフレーム単位で証明したわけではない。

配布動画は幅310–572、高さ510–614の人物を中心とした画角。自前動画の1920×1080とは画角・縦横比が異なる。この差の寄与は今回実測していない。モデル側の前処理を勝手に変更する根拠にせず、次の対照条件として残す。

## 推論・採点の条件

- 上流revision `eed438bcb49e30405cd6ccdfcccca330c134e830`。既存の導入パッチと環境を維持。
- checkpoint SHA256 `1bfd5f3312f04e4736f0a52f4ef9535916e6de9676a2a0d00c708748683fb00d` を再確認。mT5 revision `2eb15465c5dd7f72a8f7984306ad05ebc3dd1e1f`。
- conda `Uni-Sign`、Python 3.9.25、torch 2.1.1+cu121、Transformers 4.40.0、ORT 1.18.0、RTX A6000。正確な一覧は実行出力の `environment.txt`。
- pose-only、How2Sign、SLT、eval/no_grad、BF16、batch1、beam4、max_new_tokens100、max_length256。
- 各サンプル・各経路でseed42を再設定。長い3本も両経路で選択indexが完全一致することを結果から検証した。
- 配布pose経路は上流 `S2T_Dataset.load_pose` を再利用。How2Signの既定pose_dirが別データを指すため、helper内のdatasetインスタンスだけ実ファイルの親ディレクトリへ設定。`config.py` は編集していない。
- 再抽出経路は上流 `demo.online_inference.pose_extraction` と `S2T_Dataset_online` を再利用。Wholebody lightweight、16 workers、既存YOLOX/RTMW ONNX。24 ONNXセッションすべてでCUDA providerを確認。
- 両経路の部位正規化は同じ `load_part_kp`。参照英文はID・ラベル対応の検査と採点にだけ使い、forward/generateへ渡すtargetは空文字。補正・語彙制約・正解promptなし。
- 指標は上流 `SLRT_metrics.translation_performance` のcorpus BLEU1–4（13a、case mixed、exp smoothing）とROUGE-L F×100。BLEURTは追加モデル・依存を取得せず未計算。

上流 `script/eval_stage3.sh` はCSL-Daily/RGB-poseの例であり、そのまま実行していない。今回のhelperはHow2Signのdataset/model/generate/metricsを使うが、DeepSpeedを含む公式評価CLI全体を再現したものではない。全test、batch8、全件を通した乱数系列とも異なる。少数診断の数字を論文の厳密再現と呼ばない。

## 英文内容と解釈

主旨が一致した短い例：参照 **“Good forward extension.”** に対し、両経路とも冠詞・主語を補った同義の英文を生成した（配布pose側には余分な空白あり）。完全一致0件でも、一部の翻訳が成立している例になる。

他の例では、学習分布の語彙や文の構造を部分的に捉えながら、重要な意味を落としていた。

- 歯を動かして保持する説明：配布poseでは対象を鼻へ置換。再抽出では歯を保持する部分は残るが、冒頭に別の概念を追加し、対比・結論を省略。
- パスタとソースの選択：両方でチーズを省く部分等は残るが、食材名の誤認や選択肢の省略がある。
- 型をなぞって切る説明：刃物を取る表現を繰り返し、手順の重要部分を落とす。
- 台本と長い綴じ具の説明（`FZCF7kPIyOk_10-1`）：両方とも物の大きさについての文となり、主旨不一致。

12組の配布pose/再抽出の出力は厳密な文字列ではすべて異なるが、空白だけの違いもあるため、それを意味が12件全部変わったと数えない。両方に誤訳があり、再抽出で対象語が改善する例もある。平均BLEUの差だけで全例が一方向に悪化したとはいえない。

全24出力にEOSがあり、最大token列長は53。反復が起きた出力も今回の100新規token上限による打ち切りではない。全24件で正規化poseとモデル入力embeddingはfinite、strictのMissing/Unexpected keysは空。

意味評価は英語参照と生成文を主・サブエージェントが比較した質的評価であり、人間の独立評価やASL映像に基づく正解再注釈ではない。細かな評定と根拠は `outputs/20260912-how2sign-benchmark-review-c/semantic-review.md` に保存。モデル生成の文章補正には使用していない。

| サブエージェントの質的評定 | 配布pose | 再抽出pose |
|---|---:|---:|
| 完全一致 | 0 | 0 |
| 主旨概ね一致 | 1 | 2 |
| 部分一致 | 6 | 5 |
| 主旨不一致・判定困難 | 5 | 5 |

再抽出の食材例は境界的な「主旨概ね一致」で、厳格に扱えば「部分一致」になる。したがって2対1を精度差や再抽出の優位の証拠としない。共通する明瞭な主旨一致は上記の短文1例で、多数の正確な翻訳を再現したとはいえない。

## 自前不一致への結論更新・残課題

| 疑い | 今回の結果による更新 |
|---|---|
| 推論コードや重みの重大な取り違えで何も翻訳できていない | 正解に沿う短文と部分的な内容対応、配布poseでBLEU-4 14.96を確認し、優先度が下がる。全コード無欠陥の証明ではない |
| 公開デモの姿勢抽出だけが原因 | 配布pose直入力でも誤訳が多いため、唯一の説明にはならない。抽出器差の影響自体はある |
| 自前データだけに問題がある | ベンチマークの正解付きデータでも誤訳があり、支持できない。自前の表現・撮影条件が適切と証明したわけでもない |
| How2Sign用モデルの性能・分布適合の限界 | 評価内でも意味の欠落が多く、自前挨拶での失敗と併せて重視すべき候補。分布外での性能低下量は未測定 |

次に優先するなら、自前動画を**モデルへの正解入力なし**で、How2Signの人物中心の画角に近づけた派生動画と原動画で比較する。元動画は保持し、ASLに習熟した人による表現・区間境界の確認を併せる。画角や表現の差を小さくしても改善しなければ、別のASL checkpointの比較へ進む判断材料になる。

全test評価はコード再現をさらに確認できるが、今回の依頼である少数組の切り分けは完了。新規checkpointや姿勢モデル、追加依存は取得していない。大規模学習や文章補正へ拡大しない。

## 実行・再現と保存先

作業ディレクトリはプロジェクトルート。実行した取得コマンド（count12/seed42は既定値）：

```bash
python3 -B research/sign/uni-sign/scripts/download_how2sign_subset.py \
  --output-dir research/sign/uni-sign/Uni-Sign/outputs/20260912-how2sign-benchmark-download-r2
```

別の新規保存先で同じデータを再取得する場合は、上のコマンドに `--revision eab251b7fe7e8521afc0e67be98add670ea40a0d --count 12 --seed 42` を追加する。既存ディレクトリは上書きを拒否する。初回sandbox内ではDNS制限で失敗し、`download-r1` は未取得。中断された承認要求の後、ネットワーク許可下の `download-r2` で取得成功した。

実行した評価コマンド：

```bash
conda run --no-capture-output -n Uni-Sign python -B \
  research/sign/uni-sign/scripts/evaluate_how2sign_subset.py \
  research/sign/uni-sign/Uni-Sign/outputs/20260912-how2sign-benchmark-download-r2/manifest.json \
  --output-dir research/sign/uni-sign/Uni-Sign/outputs/20260912-how2sign-benchmark-evaluation-r1
```

評価workerはexit0、全経過 **57.28秒**（プロセス起動・モデル読込・姿勢抽出・生成・採点）。生成合計は配布pose4.33秒、再抽出pose4.34秒。再抽出経路の前処理合計39.33秒。いずれも1回の実行であり、warm latency統計ではない。終了後GPUは21MiB、利用率0%。

| 配置（`research/sign/uni-sign/` 起点） | 内容 |
|---|---|
| `scripts/download_how2sign_subset.py` | 新規。固定test選択、分割ZIPの部分取得、CRC/SHA記録。標準ライブラリのみ |
| `scripts/evaluate_how2sign_subset.py` | 新規。上流dataset/model/metricsによる2経路比較、原稿は採点のみ |
| `reports/2026-09-12-how2sign-test-subset.md` | 本記録 |
| `README.md` | 今回の結果・手順へのリンク追加 |
| `Uni-Sign/outputs/20260912-how2sign-benchmark-download-r2/` | 12組の動画・配布pose、選択manifest、HF tree、archive member一覧、転送範囲・CRC・SHA |
| `Uni-Sign/outputs/20260912-how2sign-benchmark-evaluation-r1/` | 24件の参照/予測/token/指標、再抽出pose cache、入力index、ログ、環境、manifest、検証結果 |
| `Uni-Sign/outputs/20260912-how2sign-benchmark-data-a/` | 取得条件の独立調査、公式CSV、MD5・全件ラベル照合、一次資料 |
| `Uni-Sign/outputs/20260912-how2sign-benchmark-review-c/` | 独立コードレビュー、12組のframe/寸法/区間照合、英文意味評定 |

各担当は取得資料調査、評価helper実装、独立レビューを分担し、主が取得・GPU・結果照合・報告統合を行った。同じファイルの同時編集や同時GPU推論なし。取得データ・自前動画・顔・ランドマークを外部へアップロードしていない。既存入力・重み・結果・上流コード・依存は上書きしていない。生データと出力はGit対象外。共有ルートのGitメタデータが無効なためstage/commitなし。

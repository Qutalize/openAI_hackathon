# 追加ASL動画07・08：Uni-Signの英文出力と原稿比較

2026-09-12。How2Sign pose-only重みで原動画2本を推論した。**2/2件で英文生成に成功し、名前の質問・自己紹介という内容に近づいた。ただし07は余分な語、08は名前の誤認があり、正確な翻訳ができたとは言えない。** 学習・英文補正は行っていない。

## 出力と意味の評価

入力はユーザー確認済みASL、出力は英語。参照は各入力ディレクトリの`script.txt`。以下の出力は未補正で、glossや人による翻訳ではない。

| ID | 参照原稿 | Uni-Sign出力 | 評価 |
|---|---|---|---|
| 07_whats_your_name_pro | What's your name? | What's your name like? | 名前について尋ねる話題と疑問文の形は一致。余分な`like`が入り、「名前は何か」から「どんな名前か」というニュアンスへずれる。近いが正確ではない |
| 08_greetings_pro | I am named Meredith. | My name is Sedrick. | 自分の名前を伝える意図は一致。`I am named`→`My name is`は妥当な言い換えだが、`Meredith`→`Sedrick`は名前の誤認であり、自己紹介の重要情報が不一致 |

意味の評価は、生成文と提供原稿の文章比較による定性的判断。映像中の指文字をASL話者が独立に読み取って正解を確認した評価ではない。話題・発話意図の部分一致は2/2だが、重要情報や質問のニュアンスまで完全に保った正訳とは扱わない。

## 定量評価

| 対象 | BLEU-4 ↑ | ROUGE-L ↑ | 参考WER ↓ | 単語編集数 / 原稿語数 | 文字列完全一致 |
|---|---:|---:|---:|---:|---:|
| 07 | 42.73 | 57.14 | 33.33% | 1 / 3 | 0/1 |
| 08 | 10.68 | 0.00 | 100.00% | 4 / 4 | 0/1 |
| 2本をまとめて採点 | 22.59 | 28.57 | 71.43% | 5 / 7 | 0/2 |

- BLEUは既存の上流実装：13a tokenization、case mixed、exponential smoothing、0–100。集計はcorpus BLEUで、文別の平均ではない。
- ROUGE-Lは上流rouge実装のF値平均×100。BLEU/ROUGEにはWER用の小文字化・句読点除去を適用しない。
- WERは小文字化、句読点除去、語中apostrophe保持の単語編集距離÷原稿語数×100。07は`like`の1語挿入。08は文面上4語とも異なるため4編集になるが、妥当な言い換えにも罰点が付くため「意味が100%間違い」という意味ではない。
- BLEU/ROUGEは正答率ではない。08のBLEUが正でも名前の正しさを示さず、ROUGEが0でも自己紹介の意図まで無関係という意味ではない。短文2本なので、数値だけで意味の正確さを判断しない。

### 以前の結果との比較

最初の01/02の保存結果はBLEU-4 2.35、ROUGE-L 5.56、参考WER170.00%。今回の07/08は数値も内容の近さも改善している。ただし別動画で、02の原稿は`Nice to meet you. How are you?`、08は自己紹介なので、集合全体の差を撮影・実演品質だけの効果とは言えない。

同じ原稿の01と07では、01の出力`We're going to choose a smaller weight strainer.`から、07の`What's your name like?`へ名前の質問に近づいた。BLEU-4は2.38→42.73、参考WERは266.67%→33.33%。同一原稿でも映像は別であり、人物・画角・動作など個々の要因の寄与は未測定。今回の各動画の推論は1回で、反復安定性は未測定。

## 入力・実行条件と確認

| ID | 入力ファイル | 寸法 | fps | 全デコードフレーム | 長さ（frames/fps） |
|---|---|---|---:|---:|---:|
| 07 | data/sign/07_whats_your_name_pro/whatisyourname.mp4 | 1280×720 | 29.970 | 90 | 3.003秒 |
| 08 | data/sign/08_greetings_pro/mynameis (2).mp4 | 1280×720 | 29.970 | 119 | 3.9706秒 |

原動画をそのまま使用し、crop・縮小・時間trimは加えていない。両方256フレーム以下で、全フレームを使用。RTMLib Wholebody lightweightで姿勢を抽出し、上流の座標・部位別正規化を適用した。英文生成には音声・正解原稿を使わず、評価補助は2件の生成後にのみ原稿を読み込む。

How2Sign / SLT / pose-only、BF16、batch1、seed42を各入力前に再設定、beam4、max_new_tokens100、max_length256、eval/no_grad。既存の[evaluate_preprocessed_self.py](../scripts/evaluate_preprocessed_self.py)と[score_saved_results.py](../scripts/score_saved_results.py)を無変更で使用。

- 上流revision：`eed438bcb49e30405cd6ccdfcccca330c134e830`
- checkpoint SHA256：`1bfd5f3312f04e4736f0a52f4ef9535916e6de9676a2a0d00c708748683fb00d`
- mT5 revision：`2eb15465c5dd7f72a8f7984306ad05ebc3dd1e1f`
- 既存Uni-Sign専用環境：Python3.9.25、PyTorch2.1.1+cu121、RTX A6000。依存一覧と全重みハッシュは保存manifest/environmentを参照。
- checkpointのMissing/Unexpected keysはともに0。全4 ONNXセッションにCUDA providerを確認。全入力・埋め込みが有限で、各フレームの検出人数は1。入力・原稿・保存poseのSHA256と出力テキストの一致を確認した。
- 全2本のworker起動・モデルロード・前処理・生成・採点は14.52秒。モデルロードは5.34秒。07は前処理2.81秒＋生成0.39秒、08は前処理2.89秒＋生成0.29秒。前処理時間にはpose抽出を含む。単発測定で、warm平均やp95ではない。

保存された正規化poseのマスク率は、07の左手22.91%・右手0%、08の左手51.02%・右手7.48%（全時間×全手点に対する割合）。これは全動画の集計で、動作していない手や画外の区間も含み得る。指文字区間だけの評価ではなく、今回の名前誤認の原因と断定できない。翻訳の信頼度はモデルから提供されず`null`。

最初の`evaluation-r1`はサンドボックス内でCUDA利用不可となり、生成前に失敗。許可された制限外実行の`evaluation-r2`で成功した。r1の失敗ログも保持した。

## 保存先・再現

- [全出力・原稿・各指標・生成token](../Uni-Sign/outputs/20260912-self-07-08-evaluation-r2/results.json)
- [実行条件・revision・重みSHA256](../Uni-Sign/outputs/20260912-self-07-08-evaluation-r2/manifest.json)
- [検証結果・計測時間](../Uni-Sign/outputs/20260912-self-07-08-evaluation-r2/verification.json)
- [07の未補正英文](../Uni-Sign/outputs/20260912-self-07-08-evaluation-r2/07_whats_your_name_pro/original/prediction.txt)、[08の未補正英文](../Uni-Sign/outputs/20260912-self-07-08-evaluation-r2/08_greetings_pro/original/prediction.txt)
- [入力manifest](../Uni-Sign/outputs/20260912-self-07-08-inputs-r1/manifest.json)、[入力manifest作成補助](../Uni-Sign/outputs/20260912-self-07-08-inputs-r1/prepare_manifest.py)。映像・pose・生出力はローカルのGit対象外領域に保存。

プロジェクトルートから実行したコマンド。再実行時は新規の`--output-dir`へ変更する。

```bash
/home/kosaki/anaconda3/envs/Uni-Sign/bin/python -B \
  research/sign/uni-sign/scripts/evaluate_preprocessed_self.py \
  --manifest research/sign/uni-sign/Uni-Sign/outputs/20260912-self-07-08-inputs-r1/manifest.json \
  --output-dir research/sign/uni-sign/Uni-Sign/outputs/20260912-self-07-08-evaluation-r2
```

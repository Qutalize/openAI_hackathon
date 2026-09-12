# 自前ASL動画2本の推論結果と精度

対象は第三者版SpaMo-Sign-VLAのHow2Sign用として配布された重み。
初回の公式Dropbox重みとは区別する。今回、保存済みの未補正英文を各動画の `script.txt` と比較した。
入力はASL、出力は英語。学習・ファインチューニングなし。正解原稿と音声は推論に使用していない。

## 結果

2本とも生成処理は正常終了したが、正解原稿の意味を再現できていない。
1本目は数字の反復、2本目はボールや守備者を見るという内容で、名前の質問・挨拶に対応しなかった。
完全一致は **0/2本（今回の標本では0%）**。モデル一般の正解率が0%という意味ではない。

| 指標 | 2本を対象とした実測値 |
|---|---:|
| BLEU-1 | 2.00 |
| BLEU-2 | 1.01 |
| BLEU-3 | 0.64 |
| BLEU-4 | 0.43 |
| ROUGE-L F1 × 100 | 6.82 |

BLEU・ROUGEは文字列の重なりを測るスコアであり、「翻訳正解率0.43%／6.82%」とは解釈しない。
意味が異なっていても一般的な語の一致により非ゼロになり得る。
意味に関する判断は生成文と原稿の目視比較であり、ASL専門家による映像の再注釈ではない。
動画2本のみの結果で、How2Signテストセット評価や論文性能の再現ではない。
モデルは信頼度を提供していない。

## 実行条件と所要時間

- コードrevision：`d34bc0b62927a5b1b1b3f4fefcc0828c3f0b9983`。
- 重みSHA256：`140d412d232407cfc3409ba5faf8bb96ede276aadf0223b156c7e3bd6ec37ee3`。
- 全871項目をstrictロード。中央crop・空間／動き特徴の交互結合は配布者の現行推論コードに準拠。
- beam=5、samplingなし、ICLなし。GPUはRTX A6000。
- 1本目の処理全体67.33秒、2本目47.91秒。特徴抽出・モデル読込等を含む個別プロセスの実測で、繰り返し計測した平均ではない。

配布重みの学習時コード・前処理と現行推論コードの完全な対応は未確認。
今回の失敗原因が重み・前処理・撮影条件のどれにあるかは、この結果だけでは特定できない。
初回の公式重みは英語指定でもドイツ語の天気文を出力しており、今回の採点対象には含めない。

## 採点方法と再現

上流 `SpaMo/utils/evaluate.py` と同じ設定で、sacrebleu 2.2.0のcorpus BLEU（13a、大小文字区別、既定のexp smoothing）、
rouge-score 0.1.2のROUGE-L（use_stemmer=True、各文F1の平均）を使用。
上流のROUGE値は0〜1だが、この報告では100倍して表記する。
完全一致は前後空白のみ除去して比較。推論は再実行せず、既存の出力ファイルを採点した。

リポジトリルートで実行：

```bash
research/sign/SpaMo/.venv/bin/python research/sign/SpaMo/scripts/score_saved_results.py \
  --pair research/sign/SpaMo/outputs/20260912-sign-vla-asl-01/result.json data/sign/01_whats_your_name/script.txt \
  --pair research/sign/SpaMo/outputs/20260912-sign-vla-asl-02/result.json data/sign/02_greetings/script.txt \
  --output research/sign/SpaMo/outputs/20260912-sign-vla-score/scores.json
```

実行済み、終了コード0。採点JSONには全文・正解原稿・各入力ファイルのSHA256・指標設定も保存した。
原文と生成全文はGit対象外の `outputs/` に保持する。

- [採点結果JSON](../outputs/20260912-sign-vla-score/scores.json)
- [1本目の推論記録](../outputs/20260912-sign-vla-asl-01/result.json)
- [2本目の推論記録](../outputs/20260912-sign-vla-asl-02/result.json)
- [重みの調査・取得・推論報告](2026-09-12-how2sign-weight-search.md)

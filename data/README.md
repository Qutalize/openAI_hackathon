# 評価用データ

英語VSR素材は `data/vsr/<原稿ID>/` にまとめる。入力言語は英語。

```text
data/vsr/
  01_daily_plans/
    script.txt          # 読み上げ原稿（Git管理）
    original.mp4        # 音声付き撮影原本（Git対象外）
    video_only.mp4      # 音声トラックなしのモデル入力（Git対象外）
  02_breakfast/
    script.txt
  03_weather/
    script.txt
  04_shopping/
    script.txt
  05_weekend/
    script.txt
  06_work_update/
    script.txt
```

原稿6本を配置済み。映像と `reference.txt` はまだ作成していない。
お題は順に「今日の予定」「朝食」「天気」「買い物」「週末」「作業報告」。
1本あたり約15〜25秒を想定（未計測）。まず1本で推論を確認し、その後に追加する。
認識しやすさは未検証であり、この素材だけで一般的な認識精度を判断しない。

## 撮影と正解文

1. `script.txt` を読み、正面から口元が見える状態で、自然な話し方で撮影する。文末に短い間を置く。
2. 確認用の音声付き原本を `original.mp4` として保存する。
3. 下記プログラムで `video_only.mp4` を作り、全候補に同じ動画を渡す。

撮影後に原稿を書き換えない。撮り直しや別話者を追加する場合は、例えば `original_p02_take02.mp4`、`video_only_p02_take02.mp4`、`reference_p02_take02.txt` と対応づけ、既存素材を上書きしない。
原稿と正解文は認識モデルのpromptに渡さず、出力との比較用に使う。
撮影日、匿名話者ID、動画SHA256、入力言語、動画長・fps・解像度、照明・向き・距離・機材、発声／無声口パク、使用許可、保存先、削除期限はローカルの実験記録に残す。未確認の値を推測で埋めない。
モデル固有の前処理結果と推論出力は `research/vsr/<model_id>/outputs/` に置く。

## 音声なし動画の作成

Python 3と、PATH上のFFmpegが必要。Pythonの追加パッケージは不要。
プロジェクトルートで実行する：

```bash
python3 research/vsr/scripts/remove_audio.py data/vsr/01_daily_plans/original.mp4
```

入力と同じディレクトリに `video_only.mp4` を作る。原本は変更しない。
最初の映像ストリームだけを再エンコードせずコピーし、音声・字幕など他のストリームは含めない。画像サイズやfpsのモデル向け調整は行わない。
出力が既に存在する場合は失敗し、上書きしない。別名を指定する場合：

```bash
python3 research/vsr/scripts/remove_audio.py data/vsr/01_daily_plans/original_p02_take02.mp4 --output data/vsr/01_daily_plans/video_only_p02_take02.mp4
```

## Git管理

`.gitignore` で `data/vsr/` の一括除外を解除し、`/data/vsr/*/*.mp4` を除外する。原稿などのテキストはGit管理可能。
既存の全体ルール `*.mp4`、その他の動画・顔ランドマーク・重みの除外は維持するため、別の階層に保存した動画もGit対象外。
個人情報や使用許可の記録はGitへ追加せず、各モデルの `outputs/` など除外済みの場所で管理する。正解文も共有可能な内容を確認してから追加する。
映像はcommitやpushではバックアップされない。
`data/sign/` などVSR以外のデータは引き続きGit対象外。

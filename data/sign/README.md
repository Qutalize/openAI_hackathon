# 撮影した手話動画

`data/vsr/` と同様に、内容ごとのディレクトリへ動画と原稿を保存する。

```text
data/sign/
  01_whats_your_name/
    original.mp4
    script.txt
  02_greetings/
    original.mp4
    script.txt
  03_i_want_soap_horizontal/
    original.mp4
    script.txt
  04_i_want_soap_vertical/
    original.mp4
    script.txt
  05_i_want_water_horizontal/
    original.mp4
    script.txt
  06_i_want_water_vertical/
    original.mp4
    script.txt
```

## 原稿と手話言語

対象手話言語は未確認。原稿の表記言語（英語・日本語）から、ASLや日本手話と判断しない。
各 `script.txt` は元ファイル名に基づく暫定原稿であり、撮影者による実際の表現内容の確認は未実施。
モデルの認識結果やglossではなく、動画の内容を記録するためのテキストとして扱う。

| 保存先 | 元ファイル名 | 暫定原稿 |
|---|---|---|
| `01_whats_your_name/` | `What's your name - Trim.mp4` | What's your name? |
| `02_greetings/` | `はじめまして_How Are you.mp4` | はじめまして。 / How are you? |
| `03_i_want_soap_horizontal/` | `I_want_soap_horizontal.mp4` | I want soap. |
| `04_i_want_soap_vertical/` | `I_want_soap_vertical.mp4` | I want soap. |
| `05_i_want_water_horizontal/` | `I_want_water_horizontal.mp4` | I want water. |
| `06_i_want_water_vertical/` | `I_want_water_vertical.mp4` | I want water. |

`03`〜`06` は2026-09-12の追加分。`horizontal` / `vertical` は元ファイル名の横・縦の区別を引き継いでいる。
追加分の原稿の表記言語は英語。対象手話言語と実際の表現内容は未確認。

`original.mp4` は受領した動画を再エンコードせず移動・改名したもの。
1本目は元ファイル名に `Trim` があり、撮影前の未編集原本かどうかは未確認。
移動前後のSHA256が一致することを確認済み。

| 動画 | SHA256 |
|---|---|
| `01_whats_your_name/original.mp4` | `f219c03cc769747427a700b935d5d3e78b9705f1e9b661489213af33f853ed10` |
| `02_greetings/original.mp4` | `14a4992d7d626131026a3c8997739f6cce977822eb3d02b4b318e69ceef36d0d` |
| `03_i_want_soap_horizontal/original.mp4` | `0caf0f2d4727d21eb680556f858563c606308eeaf83f9a9fa56887564685548d` |
| `04_i_want_soap_vertical/original.mp4` | `2331839c6d8cc1fb5777e2a307b73866f9fe823a72ffc71e577aa0f08b81caaf` |
| `05_i_want_water_horizontal/original.mp4` | `5e353da52972857e663c6f36fe49b7217f66e90ba56c568c5a91066f555162ce` |
| `06_i_want_water_vertical/original.mp4` | `80e21753c603b95f10171a3f206a9a2f374e398bdba198a38edb33d93755f141` |

既存の `.gitignore` に従い、このディレクトリの動画と原稿はローカル管理する。
モデル固有の前処理結果と推論出力は `research/sign/<model_id>/outputs/` に保存する。

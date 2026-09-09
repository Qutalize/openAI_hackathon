# モデル調査・選定計画

調査日：2026-09-08。一次資料の机上調査。重み取得、インストール、推論、GPU測定は未実施。
mainブランチ等の可変URLを確認しているため、再現実験時にはcommit/revisionを固定する。

## 読唇の比較

| 項目 | LipCoordNet | VALLR |
|---|---|---|
| 概要 | 画像系列＋口唇ランドマーク。LipNet拡張 | 映像→音素→文章の二段階をREADMEで説明 |
| 公表値 | overlapped speakersでWER 1.7%、CER 0.6% | LRS3でWER 18.7%、LRS2で20.8% |
| 公表条件 | EGCLLCを学習に使用との記載 | LRS3/LRS2の評価。自由な無音口パクの実測ではない |
| 環境の記載 | Python 3.10+、PyTorch 2.0+、dlib、FFmpeg | Python 3.10+、PyTorch 2.4.1 |
| 入手 | HFにinference.py、pretrainディレクトリ | READMEにGoogle Driveの重みリンク |
| 標準prompt | モデルカードに任意文脈入力の説明なし | 下記の公開推論経路に引数なし |
| ライセンス表記 | モデルカードはMIT | READMEはCC BY-NC 4.0 |
| 最初の検証 | 重みとlandmark依存を揃え、短動画を文章化 | CLIとコードの差を確認し、文章復元経路を確保 |

上の数値は評価データと話者分割が異なるため、1.7%と18.7%を比べて優劣を決めない。
LipCoordNetの学習GPUはRTX 3080 12GBとの記載だが、必要推論VRAMを示す値ではない。
両モデルとも自前カメラ、英語非母語話者、声を出さない口パクで性能を測り直す。
出典：[LipCoordNetモデルカード](https://huggingface.co/SilentSpeak/LipCoordNet)、[配布ファイル](https://huggingface.co/SilentSpeak/LipCoordNet/tree/main)、[VALLR README](https://github.com/MarshallT-99/VALLR)。

## タスク1：VALLRにテキストプロンプトを入れられるか

**現時点の結論：確認した公開CLIには任意テキストプロンプトの入力口がない。READMEの二段階構成がそのまま実行できるとも、まだ確認できない。**

公開コードから確認した事項：

- `config.py`のload_argsにはprompt/context引数がない。READMEのmodel_path / infer_video_pathも有効な引数として定義されていない。
- `main.py`のinferはsave_model_pathとvideos_rootを利用する。run_inferenceは音素列と特徴を返し、その経路に文章生成呼出しは見当たらない。
- load_videosは16フレームを抽出する。frame_size引数があっても、その関数内にresize処理は見当たらない。
- 推論のargmax結果を音素へ変換する箇所には、標準CTCの重複統合・blank除去の確認が必要。

出典：[config.py](https://raw.githubusercontent.com/MarshallT-99/VALLR/main/config.py)、[main.py](https://raw.githubusercontent.com/MarshallT-99/VALLR/main/main.py)。これは読んだ経路に限る判断で、論文の手法全体が不可能という意味ではない。

VALLR担当が行う実験：

1. 上流revisionを固定し、依存と重みの取得元・SHA256を記録する。
2. `python main.py --help` と実際の引数を確認する。READMEのコマンドを動作確認済みとして転載しない。
3. 下記はコード読解からの候補コマンド。V1/V2と重みの一致、crop、サイズ、正規化を確認してから実行する。

```bash
python main.py --mode infer --version V1 --save_model_path /path/to/model.pth --videos_root /path/to/preprocessed.mp4
```

4. 音素だけでなく、英語文が得られるまでを独立に確認する。公開の文章復元モデル・重み・tokenizer・呼出し方法の有無を調べ、見つからない場合は欠落として記録する。
5. 文章復元を別LLM等で実装する場合は「VALLR＋独自decoder」と別model_idにする。元論文の再現成功とは扱わない。
6. 独自decoderにtopic/vocabularyを渡せる設計は可能という推論。ただし読み取り精度の改善は未検証。まず文脈なし、正しい話題、誤った話題の3条件で比較する。
7. 正解文をpromptに入れない。空動画・無関係動画でも文脈だけから文章を生成していないか調べる。

選定ゲート：初回の検証枠（目安2時間）で文章化まで再現できなければ、VALLRを調査枠に残してLipCoordNetの疎通を優先する。両者が動かない場合は選定未完了とし、再現を阻む問題と次の検証を残す。

## タスク2：手話の候補

ASL（米国手話）と日本手話は別に選ぶ。英語読唇を採用することはASL採用を意味しない。
最初は孤立した3〜5語の認識に限定する。glossは語彙ラベルであり、それだけで自然な文の翻訳が完成するわけではない。

| 候補 | 入出力・用途 | 初回確認 | 位置づけ |
|---|---|---|---|
| WLASL公式I3D | RGB動画→ASLの単語クラス | 配布重み、クラス対応、対象単語、前処理 | ASLを実演できる場合の第一調査候補 |
| AI4Bharat OpenHands | 姿勢時系列を使う手話認識ライブラリ | 対象言語のcheckpoint、骨格定義、依存互換性 | 姿勢ベースの比較候補 |
| MediaPipe Gesture Recognizer | 手ランドマーク・既定ジェスチャークラス | 手検出、none、連続誤検出 | 参考候補。手話翻訳とは呼ばない |

WLASLにはI3D/Pose-TGCNの評価コードと重みリンクがあり、データはC-UDAの確認が必要。リンク切れ動画の再取得を前提に一日で全データを揃える計画にはしない。
[WLASL公式](https://github.com/dxli94/WLASL)

OpenHandsはモデルそのものではなくライブラリ。コードはApache 2.0表記で、データ規約は別。リポジトリには積極的な保守を終了した旨の表示があるため、環境再現を早期判定する。
[OpenHands公式](https://github.com/AI4Bharat/OpenHands)

MediaPipeの既定ジェスチャー分類は任意の連続手話の翻訳器ではない。手話モデルが使えない場合に採用するならmodality=gestureと表示する。
[Gesture Recognizer公式](https://developers.google.com/edge/mediapipe/solutions/vision/gesture_recognizer)

手話担当の完了条件：言語・3〜5語・重みURL・クラス対応・ライセンス・実行手順・速度・未知動作の失敗例を1枚の実験記録にまとめる。日本手話が必要なら日本手話のモデル/データを追加調査し、ASLモデルのラベルだけ日本語化して代用しない。

## 初回の試運転

作業場所は [VSR](../research/vsr/README.md) と [手話](../research/sign/README.md)。
まず動画1本で推論し、実行成否・出力・処理時間・導入の難しさを [テンプレート](../research/templates/REPORT_TEMPLATE.md) に記録する。
以下の定量評価は少数動画での所感を得た後に拡充する計画であり、初回実行の必須条件ではない。

## 比較を深める場合の共通評価手順

1. 同意した4人が、同じ10短文を各2回、音声なし・正面・同じ照明で録画（80区間を目安）。英語習熟度も条件として記録する。
2. 3人分を開発/閾値調整用、1人分を固定評価用に分ける。最終評価者の映像と正解はprompt調整や学習に使わない。小規模評価であり一般化性能を保証しない。
3. readmeどおりの素のモデル結果と独自補正結果を別々に評価。語彙制限を使った場合は制限なしと別条件にする。
4. WER=(置換+削除+挿入)/正解語数、CER、文完全一致、無結果率、意味の伝達成功を記録。大文字小文字・句読点正規化を固定し、評価者による採点基準も残す。
5. 空/顔なし/口が静止/横顔/短すぎる動画を負例として加え、誤って字幕を出す割合を測る。
6. 動画読込開始→結果取得は同一プロセスの単調時計で計測。前処理/推論/後処理、cold start、warm p50/p95、件数、ピークVRAMも併記する。録画時間は別に報告する。
7. 手話は単語top-1、macro-F1、語ごとの混同行列、未知動作の誤受理率を測る。読唇WERと単語分類精度を直接比較しない。

採用条件：入手/利用条件が確認でき、再現可能で、対象入力に適合し、実出力と所感を記録できていること。その後に精度、処理時間、セットアップの難しさを比較する。
GPU予算不明のため、現時点でモデルの最終採用や推論速度は決めない。

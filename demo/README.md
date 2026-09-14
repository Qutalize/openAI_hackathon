# ことばリンク

発声・読唇・日本手話・文字入力を共通の字幕に変換する会話アプリです。[design.md](designs/design.md) をもとに、[revise.md](designs/revise.md)、[revise2.md](designs/revise2.md)、[revise3.md](designs/revise3.md) の修正を反映したReact画面と、FastAPI、WebRTC、WebSocketを接続しています。1ルーム最大4人です。

## 実装状態

| 機能 | 状態 |
|---|---|
| モード選択・標準／聴覚サポート・視覚サポート画面 | 実装済み。レスポンシブ表示、キーボード操作、文字入力への切替 |
| ルーム作成・参加・退出 | 画面でID・パスワードを設定して新規作成、既存ルームへ参加。SQLite、Argon2id、HttpOnly Cookie、CSRF、ルーム分離 |
| 映像・生音声 | WebRTC mesh、シグナリング、カメラ／マイク停止、ICE再接続、TURN設定 |
| 字幕 | 文字送信、共有、自分の発言修正、重複排除、再接続snapshot |
| 画面設定 | 名前の変更と共有、日本語／英語切替、映像と字幕のサイズ調整、全モード共通の会話画面 |
| 自分のカメラ録画 | 会話開始後に端末内で録画。カメラOFFで一時停止、会話終了時に動画をダウンロード |
| 発声認識 | ローカルfaster-whisper＋Silero VAD。音声モデルの導入が必要 |
| 読唇・手話 | 特徴点抽出、区間収集、ONNX推論、本人確認、共有まで実装。独自学習済み重みの導入が必要 |
| 読み上げ | ブラウザTTS。OS・ブラウザで日本語音声が利用可能であることが必要 |
| 学習 | 別画面での特徴点収集、人物別データ分割検証、TCN学習、ONNX出力・評価・登録 |

読唇・手話の学習済み重みや学習用データは付属していません。未導入の機能は画面で明示し、認識したように見せる代替結果は返しません。登録語彙の例は `config/vocabulary.ja.json` にありますが、重みの完成を意味しません。

## インターネット経由で相手と使う（このPCから共有）

ドメイン・サーバーの契約なしで試す場合は、PowerShellを1つ開いて実行します。初回は下の「ローカル起動」に沿って依存関係を準備してください。仮想環境・依存パッケージ・モデル本体はリポジトリに含まれていません。

```powershell
# cloneしたリポジトリのルートから移動
cd .\demo
.\scripts\start.ps1 share
```

画面をビルドし、アプリとCloudflare Quick Tunnelを起動します。`cloudflared` がインストール済みならそれを使い、未導入のWindows x64環境では公式GitHubリリースから `.cache/cloudflared/` へ取得してSHA-256を検証します。管理者権限やルーターのポート開放は不要です。

起動すると次のようなURLが表示されます（これは表示例です）。

```text
共有URL: https://ランダムな名前.trycloudflare.com
```

1. **自分も相手も表示されたHTTPS URL**を開きます。相手は別のWi-Fiやモバイル回線からアクセスできます。
2. 自分が「新規ルームを作成」でID・パスワードを設定します。
3. 相手に **共有URL・ルームID・パスワード** を伝えます。相手は「既存ルームに参加」で入室します。
4. カメラ・マイクの許可を行い「会話を開始」を押します。文字だけなら入力方法「文字入力」と「文字表示で参加」で使えます。

共有中はこのPCとターミナルを起動したままにし、スリープさせないでください。**Ctrl+C**でアプリ・トンネル・認識ワーカーを停止します。再起動するとURLが変わるため、相手に新しいURLを伝えてください。通常の `backend` / `frontend` コマンドは共有時には不要です。

画面・API・WebSocketを同じHTTPS URLで配信し、そのURLだけを接続元として許可します。カメラ・マイクが使えるHTTPSを維持し、セッションCookieはSecure / HttpOnlyです。公開用のルームは `data/shared-rooms.sqlite3` に保存され、ローカル用の既存ルームとは分かれます。画面デザイン・ボタン配置・操作手順は共通です。

文字・字幕・認識用データは共有URL経由、通話の映像・音声はWebRTCで通信します。**HTTPSのトンネルだけでは、すべての回線で映像・音声を中継できません。** 共有モードではSTUNを設定しますが、携帯回線や会社ネットワークなどで接続できない場合は、次のTURN設定が必要です。文字入力はTURNなしでも利用できます。

### 映像・音声用のTURNを設定する

外部のWebRTC対応TURNサービスを使う場合、プロジェクト直下の `.env` にサービスから提供された値を設定して共有を再起動します。

```dotenv
APP_TURN_URLS=turn:YOUR_TURN_HOST:3478,turns:YOUR_TURN_HOST:5349?transport=tcp
APP_TURN_USERNAME=YOUR_TURN_USERNAME
APP_TURN_PASSWORD=YOUR_TURN_PASSWORD
APP_TURN_SHARED_SECRET=
```

URL・ポートは契約先の指定を使います。`APP_TURN_PASSWORD` はクライアント向けTURN認証情報であり、管理APIキーではありません。共有モードは設定があればTURNを有効にし、不完全な設定なら公開前に停止します。サービスの認証情報に有効期限がある場合は更新が必要です。coturnを自分で運用する場合は、従来どおり `APP_TURN_URLS` と `APP_TURN_SHARED_SECRET` を使い、USERNAME / PASSWORDは空にしてください。

### 起動オプションと問題の確認

```powershell
# ツール取得とビルドだけを準備する（公開しない）
.\scripts\start.ps1 share -PrepareOnly

# 8765番が使用中の場合
.\scripts\start.ps1 share -Port 8766

# 画面を変更していない場合、ビルドを省略
.\scripts\start.ps1 share -SkipBuild

# PowerShellのスクリプト実行ポリシーで起動できない場合の同等コマンド
.\backend\.venv\Scripts\python.exe .\scripts\share.py
```

ログは `.cache/share/run-*/server.log` と `tunnel.log` に出力します。URLが発行されない場合は、Cloudflareへの接続がネットワークで制限されていないか確認してください。既存の `.cloudflared/config.yml` または `config.yaml` がある場合はQuick Tunnelと併用できないため、自分で別名に退避してから実行してください。スクリプトは既存のトンネル設定を変更しません。

Quick Tunnelは一時的なデモ向けです。固定URL・常時稼働が必要な配信には、下の「HTTPS・TURNで配信する」の構成を使います。

共有対応の検証では、ビルドと準備コマンド、バックエンド54テスト、ビルド済み画面をローカルHTTPS / WSSで配信するE2E 6テストが成功しました。E2Eでは別ブラウザでの参加、字幕共有・修正、カメラ、マイク、4人接続、再入室、スマートフォン幅の操作を確認しています。外部公開URLの発行と、実際の別回線間でのSTUN / TURN通話は未検証です。

参考：[Cloudflare Quick Tunnels](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/)、[WebRTCのSTUN設定](https://webrtc.org/getting-started/peer-connections)、[TURNによる中継](https://webrtc.org/getting-started/turn-server)。

## ローカル起動（Windows / PowerShell）

Python 3.11〜3.13、Node.js 22、uvを使用します。このワークスペースでの検証にはPython 3.13とNode.js 22を使用しました。以下は `demo` をカレントディレクトリにして実行します。

```powershell
uv sync --project backend --extra inference --cache-dir .cache/uv --system-certs
Push-Location frontend
npm.cmd ci --cache ../.cache/npm
npm.cmd run prepare:wasm
Pop-Location
```

企業ネットワーク等でnpmの証明書検証が失敗する場合は、対応するNode.jsで `$env:NODE_OPTIONS='--use-system-ca'` をそのPowerShellセッションに設定して再実行してください。証明書検証を無効化する必要はありません。

モデルを取得します。発声のsmallモデルは数百MBあるため、初回取得に時間がかかります。スクリプトは固定revision／モデル版の取得元とSHA-256を `models/manifest.json` に記録します。

```powershell
backend/.venv/Scripts/python.exe scripts/prepare_models.py --speech --vision-assets
backend/.venv/Scripts/python.exe scripts/check_capabilities.py
```

発声だけ利用する場合は `--speech` のみで構いません。モデルを入れなくても映像通話と文字入力は動作します。発声モデルとMediaPipeアセットは開発環境で取得・動作確認していますが、clone後は上記コマンドで別途取得してください。

2つのターミナルでそれぞれ起動します。

```powershell
# ターミナル1: バックエンド
./scripts/start.ps1 backend
```

```powershell
# ターミナル2: フロントエンド
./scripts/start.ps1 frontend
```

`http://localhost:5173` を開き、次の手順で利用します。

Viteが表示する `http://127.0.0.1:5173` でも同じ操作ができます。両方を接続元の許可リストに設定しています。別のURLで配信する場合は `APP_PUBLIC_ORIGIN` に実際のURLのオリジン（例：`https://demo.example.com`、パスなし）を設定し、バックエンドを再起動してください。`localhost` と `127.0.0.1` はブラウザでは別オリジンになるため、参加後は使用するURLを揃えてください。

1. 作成する人は「新規ルームを作成」を選び、利用モード・入力方法、任意のルームIDとパスワードを設定して「ルームを作成して参加」を押します。
2. ルームIDは半角英数字・ハイフンの3〜32文字（英字は小文字に統一）、パスワードは8〜128文字です。既存IDは上書きしません。ルームの有効期間は初期設定で24時間です。
3. 相手へIDとパスワードを伝えます。相手は「既存ルームに参加」で同じID・パスワードを入力し、「会話に参加」を押します。
4. 参加後の機器確認でマイク／カメラをONにし、「会話を開始」を押します。権限や機器を利用できない場合は「文字表示で参加」を選べます。発声の字幕は発話終了後に表示されます。

作成後の入室に失敗した場合は作成済みの案内が残り、「会話に参加」で入室を再試行できます。ルームはSQLiteに保存され、パスワードはハッシュだけを保存します。CLIからの作成も引き続き利用できます：`backend/.venv/Scripts/python.exe scripts/create_room.py demo-room --hours 24`。

同じブラウザプロファイルではCookieを共有するため、複数人の検証は別ブラウザ・別プロファイル・別端末を使ってください。終了は各ターミナルでCtrl+Cです。

## 設定

- `config/app.yaml` が基本設定です。ローカルの上書きは `config/app.local.yaml` に置きます。
- g29でkaiさんのAuto-AVSRを使う場合は、`config/app.g29.example.yaml`を
  `config/app.local.yaml`へコピーします。読唇の手動撮影ではブラウザが短い動画クリップを送り、
  バックエンドが25fps・無音声MP4へ変換して、別環境の
  `research/vsr/auto_avsr/scripts/run_vsr.sh`を呼び出します。Auto-AVSRの環境・重み・補助資材が
  READMEどおり準備されていない場合、読唇は「モデル未導入」と表示されます。現在取り込まれている
  事前学習済みAuto-AVSRは英語モデルなので、日本語の読唇精度を示すものではありません。
- `room.creation_ttl_seconds` は画面で作成するルームの有効期間です（既定86400秒）。作成回数はIP単位で `security.join_attempts_per_minute` と同じ上限を設け、IDを変えても上限は共通です。
- 環境変数は `APP__SERVER__PORT` のように階層を `__` で区切ります。未知の設定は起動時にエラーとなります。
- `.env.example` から `.env` を作る場合は `APP_SESSION_SECRET` をランダム値に置き換えてください。開発時に未設定ならプロセスごとに生成します。
- config内の相対パスは起動場所にかかわらず `demo/` を基準に解決します。
- セッションと字幕はメモリ内です。再起動で失われます。最後の参加者が退出して60秒後に会話履歴を破棄します。
- サーバーは音声・映像・特徴点・字幕本文をログやファイルへ保存しません。端末では自分のカメラ映像を会話中に録画し、会話終了時に保存します。学習画面の特徴点の明示保存は別扱いです。

## 読唇・日本手話モデルを作る

1. `config/vocabulary.ja.json` に認識対象のクラスID、表示文、方式を定義します。語彙を変更したらversionも更新します。
2. `http://localhost:5173/training` を会話に参加していないブラウザで開きます。本人の同意を確認し、人物ID・クラスIDを指定して特徴点を収集します。カメラ映像は保存されません。「特徴点を保存」でJSONをローカルに保存できます。
3. 同じ人・同じ動画がtrain、validation、testをまたがないよう、`training/dataset_manifest.example.json` をコピーして実際のパスを指定します。各分割に全クラスと `unknown` が必要です。
4. 学習用依存を追加し、前処理→学習→出力→評価を実行します。

```powershell
uv sync --project backend --extra inference --extra training --cache-dir .cache/uv --system-certs
backend/.venv/Scripts/python.exe training/extract_features.py data/training/manifest.json data/training/lipread.npz
backend/.venv/Scripts/python.exe training/train_temporal.py data/training/lipread.npz data/training/lipread.pt
backend/.venv/Scripts/python.exe training/export_onnx.py data/training/lipread.pt models/lipread --version lipread-demo-v1 --license YOUR_MODEL_LICENSE
backend/.venv/Scripts/python.exe training/evaluate.py data/training/lipread.npz models/lipread
backend/.venv/Scripts/python.exe scripts/prepare_models.py --register lipread
```

手話はmanifestの `modality` を `sign` とし、出力先を `models/sign` に変えて同じ工程を行います。ONNXは `features` と `frame_mask` を入力し、`logits` を返します。読唇は `[1,64,40,4]`、手話は `[1,96,100,4]` です。モデルの入出力・点ID・語彙・前処理版が一致しない場合は利用不可になります。

評価は未知人物のテスト分割で実施します。登録表現macro-F1 0.80以上・未知表現の誤受理率5%以下という初期目標に合格すると登録できます。少数の収録でこの値が出ても一般利用の精度保証にはなりません。実際の利用者・照明・距離・背景で評価を追加してください。

モデル登録後にサーバーを再起動し、以下を実行します。3方式のいずれかが未導入なら `--require-all` は終了コード1を返します。

```powershell
backend/.venv/Scripts/python.exe scripts/prepare_models.py --verify
backend/.venv/Scripts/python.exe scripts/check_capabilities.py --require-all
```

## 操作

- 入室前の「名前」で表示名を指定できます。参加後も画面上部の名前から変更でき、相手の画面と過去の字幕の名前に反映されます。同じルームでの重複名は使用できません。
- 入室前の「画像を選択」で自分のユーザーアイコンを設定できます。PNG・JPEG・WebP（5MB以下）を中央で正方形に切り抜き、96×96のPNGに縮小します。「アイコンを削除」で標準表示に戻せます。設定画像はこのブラウザに記憶され、参加時に同じルームの相手へ共有されます。サーバーでは会話履歴と同じくメモリ内で保持し、退出した人の字幕にもアイコンを表示します。
- 右上の言語選択で日本語／Englishを切り替えます。表示言語と名前はこのブラウザに記憶します。会話本文や認識モデルの対象言語を翻訳・変更する機能ではありません。
- 会話画面は映像・文字おこし・入力欄・操作ボタンを画面内に配置します。映像と文字おこしの境界をドラッグするとサイズが変わります。境界にTabで移動し、矢印キーでも調整できます。スマートフォンでは上下のサイズを調整します。過去の字幕は字幕欄の中でスクロールできます。
- 参加者のサムネイルと大きな発話者映像の間にもスライドバーがあります。上下へのドラッグ、またはTabで選択して上下キーでサイズを調整できます。Home／Endで最小／最大にできます。
- 自分の字幕は右、相手は左に表示します。「修正」は自分の吹き出しの右下にあります。文字入力は文字おこし欄の下部です。
- 参加者の枠は名前・映像・マイク／カメラ状態を別々の領域に表示し、映像を文字やアイコンで覆わない構成です。OFFには斜線を表示します。ユーザーアイコンは参加者枠と字幕の両方に表示します。入力方式のアイコン、「参加・接続の通知を読み上げる」「ショートカットを有効にする」の設定ボタンは廃止しました。「参加者」ボタンを押しても別の画面や一覧は開きません。
- マイクとカメラのOFFは該当trackを停止します。読唇・手話・文字入力中はマイクを利用しません。
- 読唇・手話は「撮影を開始」→表現→「撮影を終了して認識」→候補を確認・修正→「送信」です。
- 候補がない場合や期限切れの場合も、文字で入力して送れます。
- 字幕の「修正」は本人の発言だけに表示されます。
- 参加者ごとの「出力」で字幕のみ／字幕＋AI読み上げ／字幕＋通常音声を選べます。詳しい違いは下表のとおりです。
- 参加者枠と発話者名の横に「発話中」「認識中」を表示します。マイクONとは別の状態で、発声区間の検出中・認識処理中に表示します。実際に読み上げが始まった字幕には「読み上げ中」と青い枠を表示し、停止・完了・一時停止で解除します。
- 映像サムネイルで表示を固定できます。「自動表示へ」で解除します。
- 簡略画面を廃止し、視覚サポートでも音声操作を含めて共通の画面に表示します。日本語TTSが利用できない場合は「文字表示で参加」を選択できます。

### 字幕と音声の出力

| 出力 | 相手の生音声 | 相手の発言の読み上げ |
|---|---|---|
| 字幕のみ | 再生しない | なし |
| 字幕＋AI読み上げ | 再生しない | 発声・手話・読唇・文字入力の確定字幕を順に読み上げる |
| 字幕＋通常音声 | 再生する | 手話・読唇・文字入力の確定字幕を読み上げる。発声字幕は修正時のみ読み上げる |

どの設定でも全発言の字幕を表示します。自分の発言や再接続で復元した過去の字幕は読み上げません。通常音声では発話中に読み上げを一時停止します。AI読み上げでは生音声をミュートし、発話中も確定字幕を読み上げます。

機器確認画面と会話画面で変更でき、選択はこのブラウザに利用モード別で保存します。初期値は聴覚サポートが字幕のみ、視覚サポートがAI読み上げ、標準が通常音声です。「文字表示で参加」は字幕のみに切り替えます。出力の変更は自分が聞く音だけに適用され、マイク・入力方法・相手の出力設定を変更しません。

AI読み上げには既存のブラウザTTSを使用します。外部AIサービスの追加設定は不要ですが、OS・ブラウザの日本語音声が必要です。再生が許可されていない場合は「音声を開始」を押してください。日本語音声がない場合は画面に案内を表示し、字幕で会話を続けられます。

### 自分のカメラ録画

会話開始時にカメラがONなら自動で録画を始めます。OFFで参加した場合は、会話中にONにした時点から始まります。録画中は映像下に赤い表示が出ます。カメラOFFで一時停止し、再度ONにすると同じ録画へ続けます。マイク音声や相手の映像・音声は録画に含めません。

「会話終了」で `kotoba-ルームID-日時.webm`（対応ブラウザによっては `.mp4`）を端末へダウンロードします。録画は終了までブラウザのメモリに保持します。長時間録画はメモリを消費するため、デモの短い会話で利用してください。録画を残す場合は、再読み込み・タブを閉じる前に「会話終了」を押してください。カメラを一度もONにしなかった会話ではファイルを作りません。録画非対応のブラウザではエラーを表示し、会話自体は継続できます。

## 検証

`designs/revise3.md` の対応では、バックエンド79テスト、読み上げの単体6テスト、Ruff、フロントエンドビルド、ローカルHTTPSのE2E 11テストを確認しました。参加者ごとの出力設定、実際のWebRTC受信音声のミュート切替、マイク状態の維持、発話・認識・読み上げ表示、2本のスライドバー、日英表示とスマートフォン幅を確認しています。読み上げはテスト用の音声合成API、認識結果の表示は認識イベントの注入で検証しており、実際の音質や認識精度の評価ではありません。

`designs/revise2.md` の対応では、バックエンド73テスト、Ruff、フロントエンドビルド、ローカルHTTPSのE2E 9テストを確認しました。画像アイコンの設定・削除・再読込時の保持、相手への共有、退出後の字幕アイコン保持、不正形式・サイズ制限、映像と名前・状態表示が重ならないことを追加検証しています。

`revise.md` の対応では、バックエンド65テスト、Ruff、フロントエンドビルド、ローカルHTTPSでのE2E 8テストを確認しました。名前変更の共有・重複名の拒否・字幕修正権限・日英設定の保持・サイズ調整・カメラON/OFFをまたぐ録画と動画の再生・カメラ未使用時は録画しない動作を含みます。画面サイズは1600×1000、1366×768、1280×720、1024×768、390×844、320×568を確認しています。

```powershell
Push-Location backend
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/ruff.exe check app tests
Pop-Location
Push-Location frontend
npm.cmd run test:unit
npm.cmd run build
npm.cmd run test:e2e
Pop-Location
```

E2Eは専用の一時DBとルームを作り、ローカルのAPI・Vite・ヘッドレスブラウザを起動します。事前に8000番と5173番を空けてください。Windowsではインストール済みEdgeを使用します。その他の環境ではPlaywright Chromiumをインストールするか、`PLAYWRIGHT_CHANNEL` を指定します。カメラは疑似デバイスです。スクリーンショットと失敗時traceは `.cache/` に出力します。

このワークスペースでは、ビルド、バックエンド33テスト、E2E 9テストが成功しました。E2Eには画面からのルーム作成と別ブラウザでの参加、重複ID・誤パスワードの拒否、作成後の入室再試行、4人のmesh接続、満員時の拒否、字幕の共有・修正、再入室、マイクのPCM送信、両方式の実MediaPipeモデルによる特徴点収集、読み上げの重複排除を含みます。Windowsの疑似カメラを安定して利用するため、E2EのブラウザだけGPUを無効にしています。

接続元エラーの修正時には、起動中の実サイトをEdgeで操作し、http://127.0.0.1:5173 と http://localhost:5173 の両方で作成・参加・字幕送受信・退出を確認しました。127.0.0.1から作成してlocalhostから別参加者が参加するE2Eも成功しています。

日本語の生成テスト音声について、PCM整形→Silero VAD→別プロセスのfaster-whisper→テキスト出力も確認しました。任意の音声ファイルで同じ経路を確認する場合は、`backend/.venv/Scripts/python.exe scripts/check_speech.py 音声ファイルのパス` を実行します。

読唇・手話それぞれの人工特徴点データで、人物別分割→前処理→TCN学習→ONNX出力→PyTorchとの出力一致→評価までの実行も確認しました。人工データのモデルは精度基準に不合格となり、配信用モデルとして登録していません。この確認は学習処理の動作確認であり、読唇・手話の認識精度を検証したものではありません。

実機での日本語認識精度、TTS音声の存在、マイクへの回り込み、4端末での通信遅延、異なるネットワーク間のTURN接続は別途確認する必要があります。モデルのロード確認や疑似カメラのE2Eだけで、設計書の全受入条件を達成したとは扱いません。

MediaPipeのWASM読み込みはclassic workerを必要とするため、`npm run dev` と `npm run build` は `src/workers/vision.worker.ts` を `public/workers/vision.js` へ事前ビルドします。ワーカーの実装を変更したときは開発サーバーを再起動してください。

## HTTPS・TURNで配信する

配信ファイルは `deploy/` にあります。この作業では外部へ配信していません。

1. `.env` に `APP_HOST`、`APP_SESSION_SECRET`、`APP_TURN_SHARED_SECRET`、`APP_TURN_URLS`、必要なら `APP_STUN_URLS` を設定します。秘密値は32文字以上のランダム値を使用します。
2. `deploy/turnserver.conf.template` を `deploy/turnserver.conf` へコピーし、TURNホスト・公開IP・共有秘密値を設定します。`deploy/certs/` へTURN用証明書を用意します。
3. MediaPipeアセット・WASM・認識重みを準備してからビルドします。
4. `docker compose --env-file .env -f deploy/compose.yaml up --build -d` で起動します。DNS、HTTPSの80/443、TURNの3478/5349、UDP 49160〜49200の到達性を配信先で設定します。
5. 配信環境のルームは `docker compose --env-file .env -f deploy/compose.yaml exec api python /app/scripts/create_room.py demo-room` で作成します。

APIは1 workerです。worker数や参加人数を増やす場合は、ルーム状態の共有ストアとSFUへの構成変更が必要です。

## 技術資料

- [FastAPI WebSockets](https://fastapi.tiangolo.com/advanced/websockets/)
- [WebRTC Peer connections](https://webrtc.org/getting-started/peer-connections)
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
- [MediaPipe Face Landmarker](https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker/web_js)
- [MediaPipe Hand Landmarker](https://developers.google.com/edge/mediapipe/solutions/vision/hand_landmarker/web_js)
- [MediaPipe Pose Landmarker](https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker/web_js)
- [ONNX Runtime Python](https://onnxruntime.ai/docs/get-started/with-python.html)

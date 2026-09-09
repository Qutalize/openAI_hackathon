# LipCoordNet 試運転

上流：[LipCoordNet](https://huggingface.co/SilentSpeak/LipCoordNet)

状態：机上調査のみ。コード取得、重み取得、依存インストール、推論は未実施。

## 最初に行うこと

重みとランドマーク検出器の取得先を確認する。画像系列と座標入力の前処理を揃え、動画1本からどの文字列が返るかを確認する。

1. 実行機材と入力動画を確認する。
2. `upstream/` に固定revisionの上流コード、`weights/` に重みと付随ファイルを配置する。
3. `.venv/` 等の専用環境を作り、成功した依存バージョンとコマンドをここに追記する。
4. 上流推論を実行し、生出力とログを `outputs/<run_id>/` に保存する。
5. [記録テンプレート](../../templates/REPORT_TEMPLATE.md) を `reports/<date>-<run_id>.md` にコピーし、出力・所感・失敗原因を記載する。

未確認の起動コマンドは実行済み手順として記載しない。調査根拠は [モデル調査](../../../docs/04-model-research.md) を参照。
自作の実行補助や前処理は必要になった時点でscriptsへ追加する。UI/APIに依存させない。

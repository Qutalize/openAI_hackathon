# VALLR 試運転

2026-09-12 Git管理更新：既存の上流コード・設定・文書をルートのGitへ集約しました。
この作業ツリーでは上流コードは配置済みで、以下の過去の準備例にある上流への `git clone`・`git checkout`・パッチの再適用は不要です。
動画・重み・生出力は引き続きローカル管理です。上流ディレクトリ全体をGit対象外とする従来の記述は、この方針で置き換えます。
取得元revision、除外資材の準備、復元方法は [Git管理の集約](../../../docs/07-git-consolidation.md) を参照してください。

上流：[VALLR](https://github.com/MarshallT-99/VALLR)

状態：V1重みのロードと、公開LRS3サンプル1本のCPU推論を確認済み。未後処理の音素クラス列までは出力したが、文章復元、prompt、認識精度は未確認。

試運転結果は [`VALLR/reports/2026-09-08-lrs3-smoke.md`](VALLR/reports/2026-09-08-lrs3-smoke.md) を参照する。

## 確認済みのuv環境

共有NFS上ではwheel展開直後のメタデータ検証が不安定だったため、環境名を `vallr-vsr` とし、ローカルファイルシステムの `~/.virtualenvs/vallr-vsr` に作成した。再構築は次を実行する。

```bash
cd research/vsr/vallr/VALLR
./scripts/setup_uv.sh
```

実行確認時はPython 3.10.21、PyTorch 2.4.1+cu121を使用した。GPUドライバは利用できずCPUで実行した。

README記載の推論引数は実装と異なる。確認済みの実装CLIは `--save_model_path` と `--videos_root` を使う。

```bash
~/.virtualenvs/vallr-vsr/bin/python main.py \
  --mode infer \
  --version V1 \
  --save_model_path checkpoints/VALLR.path \
  --videos_root /path/to/224x224-video.mp4
```

## 最初に行うこと

CLIとREADMEの差を確認する。重みのV1/V2対応と前処理を揃え、音素出力まで再現する。文章復元に必要なdecoderの有無とprompt入力の可否を別に調べる。

1. 実行機材と入力動画を確認する。
2. `upstream/` に固定revisionの上流コード、`weights/` に重みと付随ファイルを配置する。
3. `.venv/` 等の専用環境を作り、成功した依存バージョンとコマンドをここに追記する。
4. 上流推論を実行し、生出力とログを `outputs/<run_id>/` に保存する。
5. [記録テンプレート](../../templates/REPORT_TEMPLATE.md) を `reports/<date>-<run_id>.md` にコピーし、出力・所感・失敗原因を記載する。

未確認の起動コマンドは実行済み手順として記載しない。調査根拠は [モデル調査](../../../docs/04-model-research.md) を参照。
自作の実行補助や前処理は必要になった時点でscriptsへ追加する。UI/APIに依存させない。

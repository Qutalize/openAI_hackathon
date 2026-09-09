# VSRモデル選定

英語の動画入力で既存モデルを実行し、認識出力と所感を比較する。

| 候補 | 作業場所 | 状態 | 実測・所感 |
|---|---|---|---|
| VALLR | [vallr](vallr/README.md) | V1のCPU推論成功（音素クラス列まで） | 公開LRS3サンプル1本で壁時計9.32秒。文章復元・精度は未確認 |
| LipCoordNet | [lipcoordnet](lipcoordnet/README.md) | 机上調査のみ | 未実施 |

各候補で動画1本の再現から始める。まず上流の動作を確認し、その後に同じ自前動画を入力する。
入力条件や前処理がモデル間で異なる場合は明記する。
実験記録は [テンプレート](../templates/REPORT_TEMPLATE.md) を各候補のreportsへコピーする。
出典と既知の問題は [モデル調査](../../docs/04-model-research.md) を参照する。

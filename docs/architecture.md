# 構成と固定バージョン

## 固定した構成

| 要素 | バージョン |
| --- | --- |
| Immich | v3.3.1 |
| 公式ROCm推論イメージ | `v3.3.1-rocm`、DockerfileのSHA256で固定 |
| ROCm | 7.2.0 |
| rocBLAS本体 | 5.2.0.70200（ROCm 7.2の公式イメージに同梱） |
| gfx900演算データの取得元 | AMD公式ROCm 6.3.4パッケージ |
| MIGraphX | 2.15.0、公式ソースの `rocm-7.2.0` タグ |
| ONNX Runtime | 公式イメージに含まれる1.27.1 |
| OCR | PP-OCRv5_mobile |

依存パッケージのURLとSHA256は `scripts/manage.py` に記載しています。ダウンロードしたdebは展開するだけで、ホストにはインストールしません。ビルド用コンテナはCPU2コア・メモリ6 GiBに制限しています。

構成ファイルは[Immich v3.3.1の公式Compose](https://github.com/immich-app/immich/releases/download/v3.3.1/docker-compose.yml)を基にしています。固定コンテナ名を外してComposeのプロジェクト単位で分離し、ポートを変数化しています。写真とDBは公式と同じ相対パスです。

## GPU対応

実GPUはgfx902です。`HSA_OVERRIDE_GFX_VERSION=9.0.0` と `HSA_USE_SVM=0` によりgfx900として扱い、公式イメージに不足するrocBLAS演算データとMIGraphX deviceライブラリを追加します。rocBLASの共有ライブラリ本体はROCm 7.2の公式イメージに同梱されたものを維持します。

`HSA_ENABLE_SDMA=0` はデータ転送経路を変更する設定です。GPU計算は継続します。今回の実機でモデル再ロード時に発生したエラーの回避策です。

## OCR対応

3.2.0では、入力サイズごとのGPUキャッシュが適切に分かれず、OCR結果が空になる問題を独自パッチで回避していました。3.3.1には公式の入力サイズ別キャッシュとOCR入力サイズの選択処理があるため、旧版用のPythonパッチ3ファイルは同梱・適用しません。ONNX RuntimeとMIGraphX本体も公式イメージのままです。

`MACHINE_LEARNING_MODEL_REVISION=main` で従来のモデル形式を使います。この組み合わせでは公式処理系がFP32を使います。旧 `MACHINE_LEARNING_ROCM_PRECISION` と独自OCR設定3項目は削除しました。

OCR・顔特徴抽出の最大バッチを1、workerとrequest threadを1、モデル保持を3600秒にします。アプリ起動前に標準の6段階のモデル推論と、見本画像のプレビュー相当サイズを実行し、初回GPU準備を行います。検証にはONNX Runtimeの実行プロファイルを使いますが、Immichアプリの処理コードは変更しません。

モデル・計算キャッシュはプロジェクト専用ボリュームへ永続保存します。準備するのは見本で必要なサイズであり、全ての写真サイズを事前コンパイルするわけではありません。未準備のサイズが初めて使われると、追加のGPUコンパイルに時間がかかる場合があります。

新しいモデル形式のrevision `v2`、別のOCRモデル、別GPUでの動作は今回の検証対象外です。

## 既存環境との区別

このツールは新規導入用です。`install --rebuild` は同じImmichバージョン内での推論イメージ再構築に限り、旧版の `.env` や配布版と異なるCompose構成がある導入先は、書き込み前に拒否します。既存環境のバージョン更新は、DB・写真のバックアップ、公式更新手順、分離環境での検証を踏まえて別途行ってください。

## 参考

- [ImmichのGPU推論](https://docs.immich.app/features/ml-hardware-acceleration/)
- [ONNX RuntimeのMIGraphX Execution Provider](https://onnxruntime.ai/docs/execution-providers/MIGraphX-ExecutionProvider.html)
- [AMD MIGraphX公式ソース](https://github.com/ROCm/AMDMIGraphX/tree/rocm-7.2.0)

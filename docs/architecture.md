# 構成と固定バージョン

## 固定した構成

| 要素 | バージョン |
| --- | --- |
| Immich | v3.2.0 |
| 公式ROCm推論イメージ | `v3.2.0-rocm`、DockerfileのSHA256で固定 |
| ROCm / rocBLAS本体 | 7.2.0 |
| gfx900演算データの取得元 | AMD公式ROCm 6.3.4パッケージ |
| MIGraphX | 2.15.0、公式ソースの `rocm-7.2.0` タグ |
| ONNX Runtime | 公式イメージに含まれる1.25.0 |
| OCR | PP-OCRv5_mobile |

依存パッケージのURLとSHA256は `scripts/manage.py` に記載しています。ダウンロードしたdebは展開するだけで、ホストにはインストールしません。ビルド用コンテナはCPU2コア・メモリ6 GiBに制限しています。

構成ファイルは[Immich v3.2.0の公式Compose](https://github.com/immich-app/immich/releases/download/v3.2.0/docker-compose.yml)を基にしています。固定コンテナ名を外してComposeのプロジェクト単位で分離し、ポートを変数化しています。写真とDBは公式と同じ相対パスです。

## GPU対応

実GPUはgfx902です。`HSA_OVERRIDE_GFX_VERSION=9.0.0` と `HSA_USE_SVM=0` によりgfx900として扱い、公式イメージに不足するrocBLAS演算データとMIGraphX deviceライブラリを追加します。rocBLASの共有ライブラリ本体は7.2.0のままです。

`HSA_ENABLE_SDMA=0` はデータ転送経路を変更する設定です。GPU計算は継続します。今回の実機でモデル再ロード時に発生したエラーの回避策です。

## OCR対応

使用したONNX Runtime / MIGraphXの組み合わせでは、初回に別の入力サイズ用のキャッシュを読み込み、文字認識が空になる問題を確認しました。また、細かな入力サイズの違いによって長時間の追加コンパイルが発生していました。

`patches/` の3ファイルはImmich v3.2.0のソースを修正したものです。

| ファイル | 変更 |
| --- | --- |
| `ort.py` | 入力名・データ型・サイズからキャッシュ保存先を分離。初回GPU計算の重複も抑制 |
| `detection.py` | 縦横比を維持して余白を足し、1024×1024で文字検出。結果座標は元画像へ戻す |
| `recognition.py` | 文字行の幅を512単位に余白付け |

FP32、OCRバッチ1、worker1、request thread1、モデル保持3600秒を使います。OCR検出の1024×1024と、認識の幅512・1024をアプリ起動前に準備します。モデルや計算キャッシュはプロジェクト専用ボリュームへ永続保存します。

これはImmich側の独自修正です。ONNX RuntimeやMIGraphX本体のソースコードを修正したものではありません。

## 参考

- [ImmichのGPU推論](https://docs.immich.app/features/ml-hardware-acceleration/)
- [ONNX RuntimeのMIGraphX Execution Provider](https://onnxruntime.ai/docs/execution-providers/MIGraphX-ExecutionProvider.html)
- [AMD MIGraphX公式ソース](https://github.com/ROCm/AMDMIGraphX/tree/rocm-7.2.0)

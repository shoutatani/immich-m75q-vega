# 出典とライセンス

このリポジトリのコードはGNU AGPL v3で提供します。全文は `LICENSE` を参照してください。

## Immich

`patches/ort.py`、`patches/detection.py`、`patches/recognition.py` はImmich v3.2.0のソースを基にした修正版です。`compose.yaml` は同バージョンの公式Docker Compose構成を基にしています。

- 原著作権者: Immichの各貢献者
- ライセンス: GNU Affero General Public License v3
- ソース: https://github.com/immich-app/immich/tree/v3.2.0
- 改変内容: `docs/architecture.md`

## AMD ROCm / MIGraphX

AMD公式パッケージとソースをセットアップ時に取得します。生成したライブラリ、AMDパッケージ、DockerイメージそのものはGitリポジトリに含めません。各依存物には元の配布条件が適用されます。

- MIGraphX: https://github.com/ROCm/AMDMIGraphX/tree/rocm-7.2.0
- AMDパッケージ配布: https://repo.radeon.com/rocm/

## 検証画像

- `samples/astronaut.png`: NASAのEileen Collins宇宙飛行士の写真。scikit-image v0.25.2同梱画像を使用。scikit-imageの公式文書ではpublic domainと記載されています。
  - 取得元: https://github.com/scikit-image/scikit-image/blob/v0.25.2/skimage/data/astronaut.png
  - 説明: https://scikit-image.org/docs/0.25.x/api/skimage.data.html#skimage.data.astronaut
- `samples/license-sample*.png`: この検証用に作成した架空の氏名・住所を含む文字見本。実在の身分証明書ではありません。
- `samples/blank*.png`: 白紙の検証画像。

Immichの学習済みモデルは、Immichの通常の取得処理でHugging Faceなどの配布元からダウンロードします。モデル自体はこのリポジトリに含めません。

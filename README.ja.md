# ImmichをM75q-1のVega 11で動かす

[English](README.md) | 日本語

ThinkCentre M75q-1 / Ryzen 5 PRO 3400GEの内蔵GPUで、Immichの**スマート検索・顔検出と顔特徴抽出・OCR**を動かすためのセットアップです。

写真は `library`、DBは `postgres` に保存する、Immichの標準的なDocker Compose構成です。外付けHDD、外部ライブラリ、クラウドバックアップなどの個別設定は含めていません。GPU対応に必要な推論用イメージを実機でビルドします。

**Immich v3.3.1専用の非公式構成です。** 古いVegaをROCmで動かす互換設定とGPU用ライブラリを含み、OCRは3.3.1の公式処理系を使います。既存のImmichを変換・更新するツールではありません。

> **運用時の更新について：** このリポジトリは、実機検証したImmich v3.3.1に固定しています。運用中も新しい安定版やセキュリティ修正を確認し、写真とDBをバックアップしてから、公式の更新手順と独自GPUライブラリの互換性を確認してください。新しい版は、分離環境でGPU推論とOCRを再検証してから適用することをおすすめします。自動更新や既存v3.2.0環境の移行は行いません。

## 対象環境

- ThinkCentre M75q-1、Ryzen 5 PRO 3400GE、内蔵Radeon Vega 11（gfx902）。
- Ubuntu 24.04 LTS / x86_64。検証機はLinux 6.8、メモリ32 GB。
- `/dev/kfd` と `/dev/dri/renderD128` が存在すること。
- Docker EngineとDocker Compose v2が導入済みで、実行ユーザーが `docker info` を実行できること。
- Python 3.11以降、`curl`、`tar`、`dpkg-deb`、`git`。
- Docker保存先と導入先に十分な空き容量。写真用とは別に100 GiB以上を推奨。
- GitHub、AMDのパッケージ配布先、GHCR、および学習済みモデルの配布先への通信。

Dockerの導入は[Docker公式のUbuntu向け手順](https://docs.docker.com/engine/install/ubuntu/)を参照してください。セットアップは一般ユーザーで実行します。ホストのGPUドライバー、カーネル、BIOS設定は変更しません。

## 導入

M75q-1上で実行します。Mac上でGPUイメージをビルドする手順ではありません。

```bash
git clone https://github.com/shoutatani/immich-m75q-vega.git
cd immich-m75q-vega
./setup.sh
```

初期値は次のとおりです。

| 項目 | 値 |
| --- | --- |
| 導入先 | `~/immich-app` |
| ブラウザで開くポート | `2283` |
| 写真 | `~/immich-app/library` |
| DB | `~/immich-app/postgres` |
| Composeプロジェクト | `immich-m75q` |
| モデルとGPUキャッシュ | プロジェクト専用Dockerボリューム |
| OCRモデル | `PP-OCRv5_mobile`（Immichの標準値） |
| 顔認識モデル | `buffalo_l`（Immichの標準値） |
| スマート検索モデル | `ViT-B-32__openai`（Immichの標準値） |

セットアップは依存ファイルの取得・SHA256確認、gfx900向けライブラリのビルド、専用イメージの作成、顔・スマート検索・OCRの初回GPU準備、Immichの起動を順に実行します。初回は数十分かかることがあります。モデルの準備中は時間がかかってもログを確認して待ってください。

完了したら `http://M75q-1のIPアドレス:2283` を開き、通常のImmichと同じように管理者を登録します。DB用パスワードは自動生成され、導入先の `.env` に所有者だけが読める権限で保存されます。アプリ用の管理者は自動作成しません。

写真に写っている文字を検索するときは、Immichの検索タイプで「OCR」を選んでください。写真の内容を探すスマート検索とは用途が異なります。

標準と同じくポートは全インターフェースで待ち受けます。インターネットへの公開方法はこのリポジトリの対象外です。

### 別の場所やポートで試す

```bash
./setup.sh install \
  --directory "$HOME/immich-gpu-test" \
  --project immich-gpu-test \
  --port 2294
```

導入先、プロジェクト名、ポートをすべて分けてください。DB・写真・ネットワーク・キャッシュも別になります。固定コンテナ名や既存の外部ボリュームは使いません。物理GPU・CPU・メモリは同じホスト上で共有するので、大量の処理を同時実行すると競合します。

空でない未管理ディレクトリ、別環境と同じプロジェクト名、使用中のポートには導入しません。途中で通信が失敗した場合は、同じ版のソース・同じオプションで再実行できます。自動で写真やDBを削除する処理はありません。

## 動作確認

まず状態を確認します。

```bash
./setup.sh status
```

管理者登録後、次のコマンドでアプリを含めた検証を実行できます。管理者のメールとパスワードを対話入力します。

```bash
./setup.sh verify
```

この検証は見本画像をアップロードし、**この導入先の推論コンテナを一度再起動**します。画像を処理していない時間に実行してください。結果は導入先の `evidence/verification.json` に保存します。

- 日本語の免許証見本と白紙で、CPUとGPUのOCR結果を比較。
- 顔画像で、顔検出・512次元の顔特徴抽出・スマート検索の特徴抽出を確認。
- ONNX Runtimeの実行記録で、各処理にMIGraphXの実行があり、CPU実行イベントが0であることを確認。
- アプリへのアップロード、OCR結果の保存、「運転免許証」のOCR検索、顔情報の保存を確認。
- 推論コンテナを再起動し、チェックサムが異なる画像をアップロードして再検証。

新規の使い捨てテスト環境なら、検証専用管理者を自動登録できます。

```bash
./setup.sh verify --directory "$HOME/immich-gpu-test" --initialize-test-admin
```

このオプションはユーザー未登録の環境専用です。認証情報は導入先の `test-admin-credentials.json` に保存し、ログには出しません。検証画像とアカウントは確認用に残ります。

## 日常の操作

独自の導入先を使った場合は、それぞれに `--directory` を付けます。

```bash
# コンテナの状態
./setup.sh status
# 推論ログ
./setup.sh compose -- logs --tail 100 immich-machine-learning
# 停止（データは保持）
./setup.sh compose -- stop
# 再開
./setup.sh compose -- up -d
# GPUの準備をやり直す（通常は不要）
./setup.sh warmup
```

`compose` は、このツールの管理情報がある導入先だけでDocker Composeを実行します。導入先の `compose.yaml` が変更されていると検出して停止します。手動変更する場合は、導入先で通常の `docker compose` を使い、変更内容を管理してください。

## 何を変更しているか

[仕組みと固定バージョン](docs/architecture.md)にまとめています。大きく分けると以下です。

1. Vega 11を近いgfx900として扱う互換設定。
2. gfx900向けrocBLAS演算データの追加と、MIGraphXのGPU用ライブラリのビルド。
3. モデル再ロード時に問題が出たGPU転送経路の回避。
4. 3.3.1の公式処理系による入力サイズ別キャッシュと、標準モデル・見本画像の初回GPU準備。

Immichのサーバー・DB・Valkeyのイメージは公式のものを使います。変更するのは推論用イメージとその実行設定です。旧3.2.0用のOCRパッチと独自設定は削除しています。モデルのrevisionは `main`（従来のモデル形式）を使い、新しい `v2` 形式は今回の検証対象外です。

## 制限と更新

- 3400GE以外のGPU、他のOS・カーネルでの動作は未確認です。
- 検証用画像で処理系を確認します。実物の免許証や細かい文字の認識精度を保証するものではありません。
- 長い文字列などで未準備の入力サイズが発生すると、追加のGPUコンパイルが必要になる場合があります。
- 動画のGPUトランスコードは設定していません。
- バージョンを自動更新しません。同じv3.3.1用のソースを修正した開発時は、`install --rebuild` で推論イメージを作り直せます（導入先・プロジェクト名・ポートは元と同じものを指定）。写真・DB・管理者設定は保持します。`--rebuild` は同じImmichバージョン内の推論イメージ再構築用で、旧v3.2.0環境に3.3.1を混在させる操作は拒否します。ImmichやROCmの更新時はGPUライブラリの互換性を確認し、分離環境で再検証してください。
- 写真とDBのバックアップは別途必要です。[Immichのバックアップ手順](https://docs.immich.app/administration/backup-and-restore/)を参照してください。

[検証結果](docs/validation.md) / [出典とライセンス](THIRD_PARTY_NOTICES.md)

このリポジトリはGPT-6 Astraによる実機調査・修正をもとに、配布用スクリプトと検証手順へ整理しています。Immich・AMD・Lenovoの公式プロジェクトではありません。

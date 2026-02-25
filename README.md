# 会社データジェネレータ

架空の日本国内の株式会社の社内データを生成するジェネレータです。
AI エージェント開発時に「適当な社内データがないかなー」という際にご利用ください。

## 機能

- 会社情報のMarkdownから、指定ドメインの社内資料（内規・議事録・報告書・マニュアル等）を自動生成
- 対話モード（Interactive）と自動モード（Auto）をサポート
- CLI と WebUI（Gradio）の2つのインターフェース

## セットアップ

### 前提条件

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Microsoft Foundry上にデプロイされた Chat Completion モデルのエンドポイント（Entra ID 認証）
- Azure CLI ^2.76.0 ※ Foundry上のモデルにアクセス可能なアカウントでログインが必要

### インストール

```bash
uv sync
```

### 環境変数

`.env` ファイルをプロジェクトルートに作成:

```
AZURE_AI_ENDPOINT=https://your-endpoint.models.ai.azure.com
```

## 使い方

### CLI

```bash
# 対話モードで営業資料を5件生成
uv run company-data-generator examples/sample_company.md --domain 営業 --count 5

# Autoモードで人事資料を10件生成
uv run company-data-generator examples/sample_company.md --domain 人事 --count 10 --mode auto
```

### WebUI

```bash
uv run company-data-generator --web
```

ブラウザで `http://localhost:7860` にアクセスしてください。

### 開発

```bash
# テスト実行
uv run pytest

# リント
uv run ruff check src/

# フォーマット
uv run ruff format src/
```


## Azure へのデプロイ

Azure Container Apps を使ってワンコマンドでデプロイできます。

### 前提条件

- Azure CLI がインストール済みで `az login` 済みであること
- Container Apps 拡張: `az extension add --name containerapp --upgrade`

### 初回デプロイ

```bash
# リソースグループ作成
az group create --name rg-company-data-gen --location japaneast

# ソースから直接デプロイ
az containerapp up \
  --name company-data-generator \
  --resource-group rg-company-data-gen \
  --location japaneast \
  --source . \
  --ingress external \
  --target-port 7860 \
  --env-vars \
    AZURE_AI_ENDPOINT=<your-endpoint-url> \
    APP_USERNAME=<ログインユーザー名> \
    APP_PASSWORD=<ログインパスワード>
```

`APP_USERNAME` / `APP_PASSWORD` を設定すると Gradio のログイン画面が有効になります。未設定の場合は認証なしで公開されます。

### アプリ更新時

ソースコードを変更したら同じコマンドを再実行するだけです。環境変数は前回の設定が引き継がれるため省略できます。

```bash
az containerapp up \
  --name company-data-generator \
  --resource-group rg-company-data-gen \
  --source .
```

### Managed Identity の設定

システム割り当てマネージド ID を有効にする必要があります。

```bash
# 1. Container Apps のシステム割り当てマネージド ID の principalId を取得
PRINCIPAL_ID=$(az containerapp identity assign \
  --name company-data-generator \
  --resource-group rg-company-data-gen \
  --system-assigned \
  --query principalId -o tsv)

# 2. Microsoft Foundry リソースの ID を取得
FOUNDRY_ID=$(az resource show \
  --resource-group <foundry-resource-group> \
  --resource-type "Microsoft.CognitiveServices/accounts" \
  --name <foundry-resource-name> \
  --query id -o tsv)

# 3. RBAC ロールを付与 (Cognitive Services User)
az role assignment create \
  --assignee "$PRINCIPAL_ID" \
  --role "a97b65f3-24c7-4388-baec-2e87135dc908" \
  --scope "$FOUNDRY_ID"
```

### 制限
*開発時のテストはModel Router利用、ドキュメント生成数は100件で実施しています。*
*多数のドキュメントを生成しようとすると、LLMのレートリミットによりドキュメント生成が失敗する場合があります。*
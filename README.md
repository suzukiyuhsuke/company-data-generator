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


### 制限
*開発時のテストはModel Router利用、ドキュメント生成数は100件で実施しています。*
*多数のドキュメントを生成しようとすると、LLMのレートリミットによりドキュメント生成が失敗する場合があります。*
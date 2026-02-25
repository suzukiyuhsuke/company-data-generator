FROM python:3.12-slim

# uv をインストール
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# 依存関係を先にインストール（キャッシュ効率化）
COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev --no-install-project

# アプリケーションコードをコピー
COPY . .
RUN uv sync --no-dev

EXPOSE 7860

CMD ["uv", "run", "company-data-generator", "--web", "--port", "7860"]

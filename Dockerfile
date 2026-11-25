FROM python:3.14-slim

WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir \
    "asyncpg>=0.31.0" \
    "fastapi>=0.162.4" \
    "fastembed>=0.7.0" \
    "langchain>=1.3.14" \
    "langchain-community>=0.4.2" \
    "langchain-milvus>=0.4.0" \
    "langchain-openai>=1.7.4" \
    "langchain-text-splitters>=1.1.2" \
    "pydantic-settings>=2.14.2" \
    "pymilvus>=3.0.0" \
    "sqlalchemy[asyncio]>=2.0.51" \
    "structlog>=26.1.0" \
    "uvicorn>=0.54.0"
COPY app ./app
COPY data ./data
COPY scripts ./scripts
EXPOSE 8020
CMD ["python", "-m", "app.main"]

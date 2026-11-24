from pathlib import Path

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

APP_ROOT = Path(__file__).resolve().parents[2]


class EnvSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(APP_ROOT / ".env",),
        env_file_encoding="utf-8",
        extra="ignore",
    )


class AppSettings(EnvSettings):
    name: str = Field(alias="APP_NAME", default="合同速查")
    host: str = Field(alias="APP_HOST", default="127.0.0.1")
    port: int = Field(alias="APP_PORT", default=8020)


class DatabaseSettings(EnvSettings):
    host: str = Field(alias="DB_HOST", default="127.0.0.1")
    port: int = Field(alias="DB_PORT", default=5432)
    name: str = Field(alias="DB_NAME", default="contractrag")
    admin_name: str = Field(alias="DB_ADMIN_NAME", default="postgres")
    user: str = Field(alias="DB_USER")
    password: str = Field(alias="DB_PASSWORD")

    def url_for(self, database: str) -> str:
        return (
            f"postgresql+asyncpg://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{database}"
        )

    @computed_field
    @property
    def url(self) -> str:
        return self.url_for(self.name)


class MilvusSettings(EnvSettings):
    host: str = Field(alias="MILVUS_HOST", default="127.0.0.1")
    port: int = Field(alias="MILVUS_PORT", default=19530)
    collection: str = Field(alias="MILVUS_COLLECTION", default="contract_chunks")

    @computed_field
    @property
    def uri(self) -> str:
        return f"http://{self.host}:{self.port}"


class EmbeddingSettings(EnvSettings):
    model: str = Field(alias="EMBEDDING_MODEL", default="BAAI/bge-small-zh-v1.5")


class LLMSettings(EnvSettings):
    api_key: str = Field(alias="DEEPSEEK_API_KEY", default="")
    model: str = Field(alias="CHAT_MODEL", default="deepseek-chat")
    base_url: str = Field(alias="DEEPSEEK_BASE_URL", default="https://api.deepseek.com")


class Settings(BaseSettings):
    app: AppSettings = Field(default_factory=AppSettings)
    db: DatabaseSettings = Field(default_factory=DatabaseSettings)
    milvus: MilvusSettings = Field(default_factory=MilvusSettings)
    embedding: EmbeddingSettings = Field(default_factory=EmbeddingSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    logging_level: str = Field(alias="LOGGING_LEVEL", default="INFO")


settings = Settings()

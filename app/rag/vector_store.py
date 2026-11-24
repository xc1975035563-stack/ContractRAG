import os

from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
from langchain_milvus import Milvus

from app.core.config import APP_ROOT, settings

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")


def build_vector_store() -> Milvus:
    embeddings = FastEmbedEmbeddings(
        model_name=settings.embedding.model,
        cache_dir=str(APP_ROOT / ".fastembed_cache"),
    )
    return Milvus(
        embedding_function=embeddings,
        collection_name=settings.milvus.collection,
        connection_args={"uri": settings.milvus.uri},
        auto_id=True,
        index_params={
            "metric_type": "COSINE",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 16},
        },
        search_params={"metric_type": "COSINE", "params": {"nprobe": 8}},
    )

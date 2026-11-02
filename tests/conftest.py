"""Fixtures compartilhadas dos testes."""
from pathlib import Path

import pytest

from emporio_agent.config import PROJECT_ROOT
from emporio_agent.data_store import DataStore
from emporio_agent.policies import load_policy_chunks
from emporio_agent.retrieval import HybridPolicyRetriever

DATA_DIR = PROJECT_ROOT / "data"


@pytest.fixture(scope="session")
def data_dir() -> Path:
    return DATA_DIR


@pytest.fixture(scope="session")
def store(data_dir) -> DataStore:
    return DataStore(data_dir)


@pytest.fixture(scope="session")
def retriever() -> HybridPolicyRetriever:
    chunks = load_policy_chunks(DATA_DIR / "políticas_da_loja.pdf")
    # Sem embeddings nos testes: retrieval 100% BM25, determinístico e offline
    settings_like = type("S", (), {
        "rag_top_k": 4,
        "enable_embeddings": False,
        "api_key": "",
        "embedding_model": "text-embedding-3-small",
        "base_url": None,
    })()
    return HybridPolicyRetriever(chunks, settings_like)

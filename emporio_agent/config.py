"""
Configurações centralizadas do agente.

Todas as variáveis podem ser definidas via arquivo `.env` (carregado manualmente,
sem dependência extra) ou diretamente no ambiente do sistema.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# Pasta raiz do projeto (um nível acima do pacote)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"


def _load_dotenv(path: Path) -> None:
    """Carrega um arquivo .env simples (CHAVE=valor) para o ambiente, sem sobrescrever o que já existe."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(PROJECT_ROOT / ".env")


@dataclass
class Settings:
    """Parâmetros de configuração do agente, todos sobrescritos por variáveis de ambiente."""

    # Provedor de LLM (SDK OpenAI; pode apontar para qualquer endpoint compatível)
    api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    base_url: str | None = field(default_factory=lambda: os.getenv("OPENAI_BASE_URL") or None)
    model: str = field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o-mini"))

    # Embeddings para o retrieval híbrido das políticas (opcional)
    embedding_model: str = field(
        default_factory=lambda: os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    )
    enable_embeddings: bool = field(
        default_factory=lambda: os.getenv("ENABLE_EMBEDDINGS", "true").lower() == "true"
    )

    # Comportamento do agente
    temperature: float = field(default_factory=lambda: float(os.getenv("AGENT_TEMPERATURE", "0.3")))
    max_tool_rounds: int = field(default_factory=lambda: int(os.getenv("MAX_TOOL_ROUNDS", "5")))
    history_max_messages: int = field(
        default_factory=lambda: int(os.getenv("HISTORY_MAX_MESSAGES", "24"))
    )

    # Retrieval das políticas
    rag_top_k: int = field(default_factory=lambda: int(os.getenv("RAG_TOP_K", "4")))

    @property
    def policies_pdf_path(self) -> Path:
        return DATA_DIR / "políticas_da_loja.pdf"


def get_settings() -> Settings:
    """Retorna as configurações (recarrega o .env a cada chamada — barato e evita estado escondido)."""
    _load_dotenv(PROJECT_ROOT / ".env")
    return Settings()

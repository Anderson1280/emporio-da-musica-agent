"""
Retrieval das políticas da loja.

Estratégia híbrida em duas camadas:
1. BM25 léxico (implementação própria, sem dependências) — sempre disponível;
2. Embeddings OpenAI (text-embedding-3-small) — ativados quando há chave e rede.

Quando ambos estão disponíveis, os resultados são combinados por
Reciprocal Rank Fusion (RRF), que é robusto a diferenças de escala entre
as duas pontuações. Se os embeddings falharem (sem chave/offline), o
sistema degrada automaticamente para BM25 puro, mantendo o agente
funcionando em qualquer ambiente.
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter

from .config import Settings
from .policies import PolicyChunk

_TOKEN_RE = re.compile(r"[a-zà-ú0-9]+")
_BOOST_SECTION = 3  # repetição dos termos do título da seção no índice
_BOOST_PARENT = 2   # repetição dos termos da seção-pai (breadcrumb) no índice

# Expansão de consulta (query expansion): mapeia palavras do cliente para os
# termos usados no manual. Necessário porque o português alterna consoantes
# na família "devolver/devolução" (v<->u), que o prefixo de 5 letras não cobre.
_EXPANSAO_CONSULTA = {
    "devolver": ["devolução", "devoluções", "devol"],
    "devolvo": ["devolução", "devoluções", "devol"],
    "devolução": ["devol"],
    "trocar": ["troca", "trocas"],
    "frete": ["entrega", "entregas"],
    "entrega": ["frete", "entregas"],
    "rastrear": ["rastreamento", "rastreio"],
    "rastreio": ["rastreamento"],
    "reembolso": ["estorno", "reembolsado"],
    "cancelar": ["cancelamento"],
    "pagar": ["pagamento", "pagamentos"],
    "comprar": ["compra", "compras"],
    "horário": ["horários"],
    "aberto": ["funcionamento"],
}


def _tokenize(text: str) -> list[str]:
    """
    Tokenização com truncamento leve (stemming por prefixo):
    além das palavras completas, indexa os radicais de 5 e 4 caracteres das
    palavras longas. O radical de 4 letras cobre flexões irregulares do
    português em que a consoante muda ("devolver" -> "devo", "devolução" ->
    "devo"), enquanto o de 5 mantém precisão para as regulares ("garantia" ->
    "garan"). Termos ubíquos que o radical curto trouxer são penalizados
    naturalmente pelo IDF do BM25.
    """
    tokens: list[str] = []
    for word in _TOKEN_RE.findall(text.lower()):
        if len(word) > 2:
            tokens.append(word)
        if len(word) >= 6:
            tokens.append(word[:5])
            tokens.append(word[:4])
    return tokens


def _expandir_consulta(query: str) -> list[str]:
    """Adiciona à consulta os termos equivalentes usados no manual (dedup)."""
    base = _tokenize(query)
    extras = [exp for tok in base for exp in _EXPANSAO_CONSULTA.get(tok, [])]
    vistos = set(base)
    for extra in extras:
        if extra not in vistos:
            base.append(extra)
            vistos.add(extra)
    return base


class BM25Index:
    """
    BM25 (Okapi) sobre os chunks de políticas.

    Parâmetros clássicos: k1=1.5 (saturação de frequência), b=0.75 (normalização
    por comprimento). Corpus pequeno -> índice em memória, sem infraestrutura.
    """

    def __init__(self, chunks: list[PolicyChunk], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1, self.b = k1, b
        self.chunks = chunks
        # Field boost: o título define o tópico da seção e o breadcrumb do pai
        # indica o tema geral, então recebem peso maior que o corpo do texto.
        # (versão simplificada do BM25F: repetir os termos do campo no índice)
        self.docs_tokens = [
            _tokenize(c.as_text())
            + _tokenize(c.section) * _BOOST_SECTION
            + _tokenize(c.parent) * _BOOST_PARENT
            for c in chunks
        ]
        self.doc_len = [len(t) for t in self.docs_tokens]
        self.avg_len = sum(self.doc_len) / max(len(self.doc_len), 1)
        self.doc_freq: Counter = Counter()
        for tokens in self.docs_tokens:
            self.doc_freq.update(set(tokens))
        self.n_docs = len(chunks)

    def _idf(self, term: str) -> float:
        df = self.doc_freq.get(term, 0)
        # Fórmula IDF com suavização (evita divisão por zero)
        return math.log(1 + (self.n_docs - df + 0.5) / (df + 0.5))

    def search(self, query: str, top_k: int = 4) -> list[tuple[PolicyChunk, float]]:
        q_tokens = _expandir_consulta(query)
        scores = []
        for idx, tokens in enumerate(self.docs_tokens):
            freq = Counter(tokens)
            score = 0.0
            for term in q_tokens:
                if term not in freq:
                    continue
                tf = freq[term]
                denom = tf + self.k1 * (1 - self.b + self.b * self.doc_len[idx] / self.avg_len)
                score += self._idf(term) * (tf * (self.k1 + 1)) / denom
            scores.append((self.chunks[idx], score))
        scores.sort(key=lambda pair: -pair[1])
        return [(chunk, s) for chunk, s in scores[:top_k] if s > 0]


class HybridPolicyRetriever:
    """Retriever das políticas: BM25 sempre; embeddings OpenAI como reforço opcional."""

    def __init__(self, chunks: list[PolicyChunk], settings: Settings) -> None:
        self.chunks = chunks
        self.settings = settings
        self.bm25 = BM25Index(chunks)
        self._embedder = None  # lazy: só inicializa na primeira consulta

    # ------------------------------------------------------------- embeddings
    def _get_embedder(self):
        """Cria o cliente de embeddings sob demanda. Retorna None se indisponível."""
        if self._embedder is not None:
            return self._embedder
        if not self.settings.enable_embeddings or not self.settings.api_key:
            return None
        try:
            from openai import OpenAI

            self._embedder = OpenAI(
                api_key=self.settings.api_key or "no-key",
                base_url=self.settings.base_url,
            )
            return self._embedder
        except Exception:
            self._embedder = None
            return None

    def _embed_search(self, query: str, top_k: int) -> list[tuple[PolicyChunk, float]]:
        """Busca por similaridade de cosseno entre embeddings dos chunks e da consulta."""
        client = self._get_embedder()
        if client is None:
            return []
        try:
            doc_vectors = self._get_chunk_embeddings(client)
            q_resp = client.embeddings.create(model=self.settings.embedding_model, input=query)
            q_vec = q_resp.data[0].embedding
            scored = []
            for chunk, vec in zip(self.chunks, doc_vectors, strict=True):
                score = _cosine(q_vec, vec)
                if score > 0.15:  # piso mínimo de relevância
                    scored.append((chunk, score))
            scored.sort(key=lambda pair: -pair[1])
            return scored[:top_k]
        except Exception:
            # Qualquer falha (rede, quota, endpoint sem embeddings) degrada para BM25
            return []

    def _get_chunk_embeddings(self, client) -> list[list[float]]:
        """Calcula (ou recupera do cache em disco) os embeddings dos chunks."""
        # Cache em disco evita recomputar embeddings a cada execução (custo/latência)
        cache_dir = self._cache_dir()
        cache_file = cache_dir / "policy_embeddings.json"
        if cache_file.exists():
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            if len(data.get("vectors", [])) == len(self.chunks):
                return data["vectors"]

        texts = [c.as_text() for c in self.chunks]
        resp = client.embeddings.create(model=self.settings.embedding_model, input=texts)
        vectors = [d.embedding for d in resp.data]
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(
            json.dumps({"model": self.settings.embedding_model, "vectors": vectors}),
            encoding="utf-8",
        )
        return vectors

    def _cache_dir(self):
        from .config import PROJECT_ROOT

        return PROJECT_ROOT / ".cache"

    # ----------------------------------------------------------------- busca
    def retrieve(self, query: str, top_k: int | None = None) -> list[PolicyChunk]:
        """
        Retorna os chunks mais relevantes para a consulta.

        Combina BM25 + embeddings via RRF quando possível; usa só BM25 quando
        embeddings não estão disponíveis.
        """
        k = top_k or self.settings.rag_top_k
        lexical = self.bm25.search(query, top_k=k * 2)
        semantic = self._embed_search(query, top_k=k * 2)

        if not semantic:
            return [chunk for chunk, _ in lexical[:k]]

        # Reciprocal Rank Fusion (k=60, valor clássico da literatura)
        rrf: dict[str, float] = {}
        chunk_by_id = {c.chunk_id: c for c in self.chunks}
        for rank, (chunk, _) in enumerate(lexical + semantic, start=1):
            rrf[chunk.chunk_id] = rrf.get(chunk.chunk_id, 0.0) + 1.0 / (60 + rank)

        ranked = sorted(rrf.items(), key=lambda kv: -kv[1])[:k]
        return [chunk_by_id[cid] for cid, _ in ranked]


def _cosine(a: list[float], b: list[float]) -> float:
    """Similaridade de cosseno entre dois vetores."""
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)

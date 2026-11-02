"""
Definição das ferramentas (function calling) e seu despacho.

Cada ferramenta combina o esquema JSON aceito pela API da OpenAI com a
função Python correspondente. A camada de negócio (DataStore / Retriever)
fica isolada aqui: o agente só conhece nomes e assinaturas.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from .data_store import DataStore
from .retrieval import HybridPolicyRetriever

# ---------------------------------------------------------------------------
# Esquemas das ferramentas (formato OpenAI tools)
# ---------------------------------------------------------------------------

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "buscar_produtos",
            "description": (
                "Busca produtos no catálogo da loja por termo livre, categoria e/ou "
                "faixa de preço máxima. Retorna os produtos ativos e em estoque, com "
                "preço final (considerando promoção ativa). Use para recomendações e "
                "consultas de disponibilidade geral."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Termo de busca livre, ex.: 'violão clássico nylon' ou 'guitarra'",
                    },
                    "category": {
                        "type": "string",
                        "description": "Filtro de categoria, ex.: 'Guitarras', 'Teclados e Pianos'",
                    },
                    "max_price": {
                        "type": "number",
                        "description": "Preço máximo em reais, ex.: 1000",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "detalhar_produto",
            "description": (
                "Consulta o detalhe de um produto específico pelo nome (preço com "
                "promoção ativa, estoque atual e especificações técnicas). Use quando "
                "o cliente citar um modelo pelo nome."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Nome do produto, ex.: 'Takamine GD20' ou 'Yamaha C40'",
                    },
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_pedido",
            "description": (
                "Consulta status, código de rastreio e entrega prevista de um pedido. "
                "Exige o número do pedido e/ou o telefone cadastrado do cliente "
                "(proteção de dados). Use para perguntas do tipo 'onde está meu pedido'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "integer",
                        "description": "Número do pedido, ex.: 7",
                    },
                    "phone": {
                        "type": "string",
                        "description": "Telefone cadastrado do cliente, ex.: '(67) 99812-3456'",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "listar_promocoes",
            "description": (
                "Lista as promoções vigentes (apenas as ativas), com preço original, "
                "desconto e preço final. Use para perguntas sobre ofertas e descontos."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "buscar_politicas",
            "description": (
                "Consulta o Manual de Políticas da loja: horários de funcionamento, "
                "formas de pagamento e parcelamento, trocas e devoluções, frete e "
                "entregas, garantia, promoções e privacidade (LGPD). Use SEMPRE que a "
                "pergunta envolver regras, prazos ou procedimentos da loja."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Consulta em linguagem natural, ex.: prazo para devolução",
                    },
                },
                "required": ["query"],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Execução das ferramentas
# ---------------------------------------------------------------------------

class ToolExecutor:
    """Mantém as dependências (dados, retrieval) e executa as ferramentas por nome."""

    def __init__(self, store: DataStore, retriever: HybridPolicyRetriever) -> None:
        self.store = store
        self.retriever = retriever
        self._registry: dict[str, Callable[..., dict]] = {
            "buscar_produtos": self._buscar_produtos,
            "detalhar_produto": self._detalhar_produto,
            "consultar_pedido": self._consultar_pedido,
            "listar_promocoes": self._listar_promocoes,
            "buscar_politicas": self._buscar_politicas,
        }

    @property
    def names(self) -> list[str]:
        return list(self._registry)

    def execute(self, name: str, arguments_json: str) -> str:
        """
        Executa uma ferramenta e devolve o resultado como string JSON
        (formato exigido pela API ao responder uma tool_call).
        """
        try:
            args = json.loads(arguments_json or "{}")
        except json.JSONDecodeError:
            return json.dumps({"erro": "argumentos inválidos (não é JSON)"}, ensure_ascii=False)

        fn = self._registry.get(name)
        if fn is None:
            return json.dumps({"erro": f"ferramenta desconhecida: {name}"}, ensure_ascii=False)
        try:
            result = fn(**args)
        except TypeError as exc:
            result = {"erro": f"argumentos incorretos: {exc}"}
        return json.dumps(result, ensure_ascii=False, default=str)

    # ----------------------------------------------------------- ferramentas
    def _buscar_produtos(
        self,
        query: str = "",
        category: str | None = None,
        max_price: float | None = None,
    ) -> dict:
        products = self.store.search_products(query=query, category=category, max_price=max_price)
        if not products:
            return {
                "resultado": [],
                "observacao": (
                    "Nenhum produto encontrado. Dica: tente termos mais gerais, outra "
                    "categoria ou remova filtros de preço."
                ),
            }
        return {"resultado": products}

    def _detalhar_produto(self, name: str) -> dict:
        product = self.store.find_product_by_name(name)
        if product is None:
            similar = self.store.search_products(query=name, in_stock_only=False, limit=4)
            return {
                "encontrado": False,
                "sugestoes_parecidas": [p["name"] for p in similar],
            }
        return {"encontrado": True, **product}

    def _consultar_pedido(self, order_id: int | None = None, phone: str | None = None) -> dict:
        order = self.store.get_order(order_id=order_id, phone=phone)
        if order is None:
            return {
                "encontrado": False,
                "observacao": (
                    "Pedido não localizado. Confirme o número do pedido e/ou o telefone "
                    "cadastrado (com DDD)."
                ),
            }
        return {"encontrado": True, **order}

    def _listar_promocoes(self) -> dict:
        promos = self.store.list_active_promotions()
        if not promos:
            return {"resultado": [], "observacao": "Nenhuma promoção ativa no momento."}
        return {"resultado": promos}

    def _buscar_politicas(self, query: str) -> dict:
        chunks = self.retriever.retrieve(query)
        if not chunks:
            return {"resultado": [], "observacao": "Nenhum trecho do manual encontrado."}
        return {
            "resultado": [
                {"secao": c.section, "pagina": c.page, "texto": c.content[:2500]}
                for c in chunks
            ]
        }

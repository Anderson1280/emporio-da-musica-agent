"""
Camada de acesso aos dados operacionais da loja (CSVs).

Carrega e normaliza as tabelas de produtos, categorias, clientes, pedidos,
itens de pedido e promoções em memória (o volume é pequeno: <100 linhas por
tabela), oferecendo métodos de consulta determinísticos usados pelas
ferramentas de function calling.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import pandas as pd

# Mapeamento dos status de pedido do CSV -> texto amigável em português
ORDER_STATUS_PT = {
    "pending": "pendente (aguardando confirmação do pagamento)",
    "confirmed": "confirmado (em preparação)",
    "paid": "pago (preparando para envio)",
    "shipped": "enviado (em trânsito)",
    "delivered": "entregue",
    "cancelled": "cancelado",
}

# Formas de pagamento do CSV -> texto amigável
PAYMENT_METHOD_PT = {
    "pix": "PIX",
    "credit_1x": "cartão de crédito (1x)",
    "credit_2x": "cartão de crédito (2x)",
    "credit_3x": "cartão de crédito (3x)",
    "credit_6x": "cartão de crédito (6x)",
    "credit_10x": "cartão de crédito (10x)",
    "credit_12x": "cartão de crédito (12x)",
    "debit": "cartão de débito",
    "boleto": "boleto bancário",
}

PRODUCT_COLUMNS = [
    "product_id", "name", "category", "price", "description",
    "stock", "status", "promotion_name", "discount_percent",
    "final_price",
]


def _normalize_text(value: object) -> str:
    """Minúsculas + remove acentos, para buscas tolerantes ('violão' ~ 'violao')."""
    text = str(value).lower()
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def _fmt_price(value: float) -> str:
    """Formata preço no padrão brasileiro: 1234.5 -> 'R$ 1.234,50'."""
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class DataStore:
    """Encapsula a carga, o tratamento e a consulta das tabelas CSV da loja."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = Path(data_dir)

        self.products = self._load("products.csv")
        self.categories = self._load("categories.csv")
        self.customers = self._load("customers.csv")
        self.orders = self._load("orders.csv")
        self.order_items = self._load("order_items.csv")
        self.promotions = self._load("promotions.csv")

        self._prepare_products()
        self._prepare_orders()

    # ------------------------------------------------------------------ carga
    def _load(self, filename: str) -> pd.DataFrame:
        path = self.data_dir / filename
        return pd.read_csv(path)

    def _prepare_products(self) -> None:
        """Tratamento da tabela de produtos: tipos, nomes de categoria e promoção ativa."""
        df = self.products
        df["price_brl"] = pd.to_numeric(df["price_brl"], errors="coerce")
        df["stock_quantity"] = pd.to_numeric(df["stock_quantity"], errors="coerce").fillna(0).astype(int)

        # Traduz specs de JSON para dict Python (usado em detalhes de produto)
        df["specs"] = df["specs"].apply(
            lambda s: json.loads(s) if isinstance(s, str) and s.strip().startswith("{") else {}
        )

        # Nome amigável da categoria
        cat_map = dict(zip(self.categories["category_id"], self.categories["name"], strict=True))
        df["category_name"] = df["category_id"].map(cat_map).fillna("Outros")

        # Promoção ATIVA por produto (descontos inativos são ignorados — política 6.2)
        active_promos = self.promotions[self.promotions["is_active"] == 1]
        promo_map = {
            row.product_id: (row.description, float(row.discount_percent))
            for row in active_promos.itertuples()
        }
        df["promotion_name"] = df["product_id"].map(lambda p: promo_map.get(p, (None, 0.0))[0])
        df["discount_percent"] = df["product_id"].map(lambda p: promo_map.get(p, (None, 0.0))[1])
        df["final_price"] = (df["price_brl"] * (1 - df["discount_percent"] / 100)).round(2)

    def _prepare_orders(self) -> None:
        """Tratamento da tabela de pedidos: datas e itens agregados por pedido."""
        self.orders["order_date"] = pd.to_datetime(self.orders["order_date"], errors="coerce")
        self.orders["estimated_delivery"] = pd.to_datetime(
            self.orders["estimated_delivery"], errors="coerce"
        )
        self.orders["total_brl"] = pd.to_numeric(self.orders["total_brl"], errors="coerce")

        # Itens por pedido: [{product_id, quantity, name}, ...]
        items = self.order_items.merge(
            self.products[["product_id", "name"]], on="product_id", how="left"
        )
        grouped = items.groupby("order_id").apply(
            lambda g: [{"product_id": int(r.product_id), "quantity": int(r.quantity), "name": r.name}
                       for r in g.itertuples()],
            include_groups=False,
        )
        self.orders["items"] = self.orders["order_id"].map(grouped).apply(
            lambda v: v if isinstance(v, list) else []
        )

    # ------------------------------------------------------------- consultas
    def search_products(
        self,
        query: str = "",
        category: str | None = None,
        max_price: float | None = None,
        in_stock_only: bool = True,
        limit: int = 8,
    ) -> list[dict]:
        """Busca produtos por termo livre (nome/descrição/espécies) com filtros opcionais."""
        df = self.products[self.products["status"] == "active"]

        if in_stock_only:
            df = df[df["stock_quantity"] > 0]

        if query:
            q = _normalize_text(query)
            # Campo concatenado para busca livre (nome + descrição + categoria)
            haystack = (
                df["name"].map(_normalize_text) + " | " +
                df["description"].map(_normalize_text) + " | " +
                df["category_name"].map(_normalize_text)
            )
            # Máscara acumulada no índice original (evita desalinhamento ao filtrar em cascata)
            mask = pd.Series(True, index=df.index)
            for term in q.split():
                mask &= haystack.str.contains(re.escape(term), regex=True, na=False)
            df = df[mask]

        if category:
            cat = _normalize_text(category)
            df = df[df["category_name"].map(_normalize_text).str.contains(cat, na=False)]

        if max_price is not None:
            # Compara pelo preço FINAL (com promoção ativa), para refletir a oferta real
            df = df[df["final_price"] <= max_price]

        # Mais baratos primeiro: ajuda o cliente a ver boas opções
        df = df.sort_values("final_price").head(limit)
        return [self._product_summary(row) for row in df.itertuples()]

    def find_product_by_name(self, name: str) -> dict | None:
        """Encontra o produto mais próximo do nome informado (busca tolerante a acentos)."""
        target = _normalize_text(name)
        candidates = self.products[self.products["status"] == "active"]

        # 1) match exato normalizado
        exact = candidates[candidates["name"].map(_normalize_text) == target]
        # 2) todos os termos do nome do produto contidos no que foi pedido
        if exact.empty:
            mask = candidates["name"].map(
                lambda n: all(w in target for w in _normalize_text(n).split())
            )
            exact = candidates[mask]
        # 3) match parcial: todos os termos da busca aparecem no nome do produto
        if exact.empty:
            words = [w for w in target.split() if len(w) >= 3]
            mask = candidates["name"].map(
                lambda n: all(any(w in part for part in _normalize_text(n).split()) for w in words)
            )
            exact = candidates[mask]
        if exact.empty:
            return None

        # Preferir o mais barato em caso de empate semântico
        row = exact.sort_values("final_price").iloc[0]
        return self._product_detail(row)

    def get_order(self, order_id: int | None = None, phone: str | None = None) -> dict | None:
        """Consulta pedido por número e/ou telefone do cliente (proteção de dados — LGPD)."""
        if order_id is None and not phone:
            return None

        df = self.orders
        if order_id is not None:
            df = df[df["order_id"] == int(order_id)]
        if phone:
            digits = re.sub(r"\D", "", str(phone))
            cust_ids = self.customers[
                self.customers["phone"].map(lambda p: re.sub(r"\D", "", str(p))) == digits
            ]["customer_id"]
            df = df[df["customer_id"].isin(cust_ids)]

        if df.empty:
            return None

        row = df.sort_values("order_date").iloc[-1]  # pedido mais recente em caso de ambiguidade
        customer = self.customers[self.customers["customer_id"] == row["customer_id"]]
        return {
            "order_id": int(row["order_id"]),
            "customer_name": customer.iloc[0]["name"] if not customer.empty else "cliente",
            "order_date": row["order_date"].strftime("%d/%m/%Y") if pd.notna(row["order_date"]) else None,
            "status": ORDER_STATUS_PT.get(str(row["status"]), str(row["status"])),
            "total": _fmt_price(float(row["total_brl"])),
            "payment_method": PAYMENT_METHOD_PT.get(str(row["payment_method"]), str(row["payment_method"])),
            "tracking_code": row["tracking_code"] if pd.notna(row["tracking_code"]) else None,
            "estimated_delivery": (
                row["estimated_delivery"].strftime("%d/%m/%Y")
                if pd.notna(row["estimated_delivery"]) else None
            ),
            "items": row["items"],
            "notes": row["notes"] if pd.notna(row["notes"]) else None,
        }

    def list_active_promotions(self, limit: int = 10) -> list[dict]:
        """Lista promoções vigentes com preço original e final (transparência — política 6.2)."""
        df = self.products[
            (self.products["promotion_name"].notna()) & (self.products["status"] == "active")
        ].sort_values("discount_percent", ascending=False).head(limit)
        return [
            {
                "product_id": int(r.product_id),
                "name": r.name,
                "category": r.category_name,
                "original_price": _fmt_price(r.price_brl),
                "discount_percent": float(r.discount_percent),
                "final_price": _fmt_price(r.final_price),
                "promotion_name": r.promotion_name,
                "stock": int(r.stock_quantity),
            }
            for r in df.itertuples()
        ]

    # ------------------------------------------------------------ formatação
    def _product_summary(self, row) -> dict:
        price_line = _fmt_price(row.final_price)
        if row.discount_percent > 0:
            price_line += f" (de {_fmt_price(row.price_brl)} por {row.promotion_name})"
        return {
            "product_id": int(row.product_id),
            "name": row.name,
            "category": row.category_name,
            "price": price_line,
            "stock": int(row.stock_quantity),
            "short_description": str(row.description)[:120],
        }

    def _product_detail(self, row) -> dict:
        detail = self._product_summary(row)
        detail.update(
            {
                "price_original": _fmt_price(row.price_brl),
                "discount_percent": float(row.discount_percent),
                "final_price_fmt": _fmt_price(row.final_price),
                "available": int(row.stock_quantity) > 0,
                "specs": row.specs if isinstance(row.specs, dict) else {},
                "full_description": str(row.description),
            }
        )
        return detail


def format_price(value: float) -> str:
    """Formatação de preço exposta para os demais módulos."""
    return _fmt_price(value)

"""Testes da camada de dados (DataStore)."""
from emporio_agent.data_store import DataStore, format_price


def test_tabela_produtos_normalizada(store: DataStore):
    assert len(store.products) == 65
    # Categoria traduzida, preço numérico e promoção calculada
    assert store.products["category_name"].notna().all()
    assert store.products["price_brl"].notna().all()


def test_busca_violao_ate_mil_reais(store: DataStore):
    resultados = store.search_products(query="violão", max_price=1000.0)
    assert resultados, "deveria encontrar violões até R$ 1000"
    # Pelo menos um produto da categoria "Violões" no resultado, e todos em estoque
    ids = {p["product_id"] for p in resultados}
    categorias = store.products.loc[store.products["product_id"].isin(ids), "category_name"]
    assert (categorias == "Violões").any(), "pelo menos um violão deveria aparecer"
    assert all(p["stock"] > 0 for p in resultados)
    # Verifica o filtro de preço final (com promoção) no dataframe de origem
    ids = {p["product_id"] for p in resultados}
    precos = store.products.loc[store.products["product_id"].isin(ids), "final_price"]
    assert (precos <= 1000.0).all()


def test_busca_tolerante_sem_acento(store: DataStore):
    com_acento = store.search_products(query="violão nylon")
    sem_acento = store.search_products(query="violao nylon")
    assert [p["name"] for p in com_acento] == [p["name"] for p in sem_acento]


def test_produtos_esgotados_nao_aparecem_por_padrao(store: DataStore):
    for p in store.search_products(query=""):
        assert p["stock"] > 0


def test_detalhe_produto_com_promocao_ativa(store: DataStore):
    # Pega um produto com promoção ativa no dataset
    df = store.products[store.products["promotion_name"].notna()]
    assert not df.empty, "o dataset deveria ter promoção ativa"
    nome = df.iloc[0]["name"]
    detalhe = store.find_product_by_name(nome)
    assert detalhe is not None
    assert detalhe.get("encontrado", True)
    assert detalhe["final_price_fmt"] <= detalhe["price_original"]


def test_produto_inexistente_retorna_none(store: DataStore):
    assert store.find_product_by_name("Instrumento Quantum XYZ 123") is None


def test_consulta_pedido_por_id(store: DataStore):
    pedido = store.get_order(order_id=7)
    assert pedido is not None
    assert pedido["order_id"] == 7
    assert pedido["status"]
    assert pedido["items"]


def test_consulta_pedido_por_telefone(store: DataStore):
    # Telefone do cliente 1 (Lucas Mendes da Silva)
    pedido = store.get_order(phone="(67) 99812-3456")
    assert pedido is not None
    assert pedido["customer_name"] == "Lucas Mendes da Silva"


def test_telefone_incorreto_nao_vaza_dados(store: DataStore):
    assert store.get_order(phone="(11) 00000-0000") is None
    # Pedido existente consultado com telefone de outra pessoa -> nada
    assert store.get_order(order_id=1, phone="(67) 99654-7821") is None


def test_promocoes_ativas_tem_desconto(store: DataStore):
    promos = store.list_active_promotions()
    assert promos, "deveria existir pelo menos uma promoção ativa"
    for p in promos:
        assert p["discount_percent"] > 0
        assert "de" in p["original_price"] or p["original_price"].startswith("R$")


def test_formato_preco_brasileiro():
    assert format_price(1234.5) == "R$ 1.234,50"
    assert format_price(429.9) == "R$ 429,90"

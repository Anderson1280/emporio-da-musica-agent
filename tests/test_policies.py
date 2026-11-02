"""Testes da extração do manual de políticas e do retrieval."""
from pathlib import Path

from emporio_agent.policies import load_policy_chunks


def test_manual_gera_chunks(data_dir: Path):
    chunks = load_policy_chunks(data_dir / "políticas_da_loja.pdf")
    assert len(chunks) >= 10, "manual completo deve gerar ao menos 10 seções"


def test_secoes_criticas_presentes(data_dir: Path):
    chunks = load_policy_chunks(data_dir / "políticas_da_loja.pdf")
    texto_total = " ".join(c.section for c in chunks)
    for esperado in ["Horário de Funcionamento", "Formas de Pagamento", "Trocas"]:
        assert esperado.lower() in texto_total.lower(), f"seção ausente: {esperado}"


def test_chunk_devolucao_tem_prazo_7_dias(data_dir: Path):
    chunks = load_policy_chunks(data_dir / "políticas_da_loja.pdf")
    devolucao = next(c for c in chunks if "Arrependimento" in c.section)
    assert "7" in devolucao.content, "deve citar o prazo de 7 dias"
    assert "reembolso" in devolucao.content.lower()


def test_retrieval_acha_secao_certa(retriever):
    casos = [
        ("posso devolver meu pedido?", "Arrependimento"),
        ("quais formas de pagamento vocês aceitam?", "Pagamento"),
        ("abrem sábado?", "Horário de Funcionamento"),
        ("qual a garantia do violão?", "Garantia"),
        ("frete para fora de Campo Grande", "Entregas"),
    ]
    for pergunta, esperado in casos:
        resultados = retriever.retrieve(pergunta, top_k=2)
        secoes = [c.section for c in resultados]
        assert any(esperado.lower() in s.lower() for s in secoes), (
            f'"{pergunta}" deveria recuperar seção com "{esperado}"; obtido: {secoes}'
        )


def test_retrieval_retorna_poucos_chunks(retriever):
    resultados = retriever.retrieve("trocas e devoluções", top_k=4)
    assert 1 <= len(resultados) <= 4

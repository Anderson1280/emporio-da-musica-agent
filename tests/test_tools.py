"""Testes das ferramentas de function calling e do loop do agente (com LLM simulado)."""
import json
from types import SimpleNamespace

from emporio_agent.tools import TOOL_SCHEMAS, ToolExecutor


# ---------------------------------------------------------------- executor
def test_executor_registra_todas_as_ferramentas(retriever, store):
    executor = ToolExecutor(store, retriever)
    schema_names = {s["function"]["name"] for s in TOOL_SCHEMAS}
    assert schema_names == set(executor.names)


def test_buscar_produtos_via_executor(retriever, store):
    executor = ToolExecutor(store, retriever)
    # Guitarras do catálogo partem de R$ 5.400, então a faixa usa esse piso real
    out = json.loads(executor.execute("buscar_produtos", '{"query": "guitarra", "max_price": 8000}'))
    assert out["resultado"], "deveria encontrar guitarras até R$ 8000"
    assert "price" in out["resultado"][0]


def test_argumentos_invalidos_nao_explodem(retriever, store):
    executor = ToolExecutor(store, retriever)
    out = json.loads(executor.execute("buscar_produtos", "não é json"))
    assert "erro" in out

    out = json.loads(executor.execute("ferramenta_inexistente", "{}"))
    assert "erro" in out


def test_consultar_pedido_protege_dados(retriever, store):
    executor = ToolExecutor(store, retriever)
    out = json.loads(executor.execute("consultar_pedido", '{"order_id": 7}'))
    assert out["encontrado"] is True

    # Telefone de outra pessoa: não revela o pedido
    out = json.loads(executor.execute("consultar_pedido", '{"order_id": 7, "phone": "(11) 99999-8888"}'))
    assert out["encontrado"] is False


def test_buscar_politicas_retorna_secoes(retriever, store):
    executor = ToolExecutor(store, retriever)
    out = json.loads(executor.execute("buscar_politicas", '{"query": "prazo devolução"}'))
    assert out["resultado"]
    assert out["resultado"][0]["secao"]
    assert out["resultado"][0]["pagina"] >= 1


# ------------------------------------------------------------- agente (fake LLM)
class _FakeMessage:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls


class _FakeToolCall:
    def __init__(self, name, arguments):
        self.id = "call_test_1"
        self.function = type("F", (), {"name": name, "arguments": arguments})()


class _FakeChoice:
    def __init__(self, message):
        self.message = message


class _FakeResponse:
    def __init__(self, message):
        self.choices = [_FakeChoice(message)]


class FakeLLM:
    """Simula dois ciclos: 1) pede ferramenta, 2) responde com o resultado."""

    def __init__(self, tool_name, tool_args, final_answer):
        self.tool_name = tool_name
        self.tool_args = tool_args
        self.final_answer = final_answer
        self.calls = 0
        self.received_messages = None

    def create(self, **kwargs):
        self.calls += 1
        self.received_messages = kwargs.get("messages")
        if self.calls == 1:
            return _FakeResponse(_FakeMessage(tool_calls=[_FakeToolCall(self.tool_name, self.tool_args)]))
        tool_result = self.received_messages[-1]["content"]
        return _FakeResponse(_FakeMessage(content=f"{self.final_answer} [{tool_result[:40]}]"))


def test_agente_executa_loop_de_ferramentas(monkeypatch, retriever, store):
    from emporio_agent.agent import AssistenteEmporio

    agent = AssistenteEmporio.__new__(AssistenteEmporio)
    # Monta manualmente para não chamar a API da OpenAI
    from emporio_agent.config import Settings
    from emporio_agent.persona import build_system_prompt
    from emporio_agent.tools import ToolExecutor

    settings = Settings()
    agent.settings = settings
    agent.store = store
    agent.retriever = retriever
    agent.executor = ToolExecutor(store, retriever)
    agent.system_prompt = build_system_prompt()
    agent.history = []
    agent._session_log = []
    agent._log_tool = lambda *a, **k: None
    agent._save_session = lambda: None
    agent._append = lambda role, content: agent.history.append({"role": role, "content": content})
    agent._prune_history = lambda: None

    fake = FakeLLM("buscar_produtos", '{"query": "violão", "max_price": 1000}', "Achei estes violões!")
    # Injeta um cliente OpenAI simulado (sem rede) direto no objeto do agente
    agent.client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=fake.create))
    )
    resposta = agent.reply("Quais violões até R$ 1000?")

    assert fake.calls == 2, "deveria fazer 2 chamadas: tool + resposta final"
    assert "Achei estes violões" in resposta
    assert agent.history[0]["role"] == "user"
    assert agent.history[-1]["role"] == "assistant"

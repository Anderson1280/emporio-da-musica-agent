"""
Núcleo do agente de atendimento.

Implementa o loop clássico de function calling com o SDK OpenAI:

    usuário -> LLM (com ferramentas) --(tool_calls)--> executor -> resultados
                     ^                                             |
                     |---------------------------------------------+
                     +--> até o LLM devolver a resposta final

O histórico da conversa é mantido em memória, com poda das mensagens mais
antigas para controlar o tamanho do contexto (o system prompt é sempre
preservado). Cada sessão também é gravada em JSON local para auditoria
da loja.
"""
from __future__ import annotations

import json
import time
from collections.abc import Generator
from typing import Any

from openai import OpenAI

from .config import PROJECT_ROOT, Settings, get_settings
from .data_store import DataStore
from .persona import build_system_prompt
from .policies import load_policy_chunks
from .retrieval import HybridPolicyRetriever
from .tools import TOOL_SCHEMAS, ToolExecutor


class AssistenteEmporio:
    """Agente conversacional da Empório da Música."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.store = DataStore(PROJECT_ROOT / "data")
        chunks = load_policy_chunks(self.settings.policies_pdf_path)
        self.retriever = HybridPolicyRetriever(chunks, self.settings)
        self.executor = ToolExecutor(self.store, self.retriever)

        self.client = OpenAI(
            api_key=self.settings.api_key or "no-key",
            base_url=self.settings.base_url,
        )
        self.system_prompt = build_system_prompt()
        self.history: list[dict[str, Any]] = []
        self._session_log: list[dict[str, Any]] = []

    # --------------------------------------------------------------- conversa
    def reply(self, user_message: str) -> str:
        """
        Processa uma mensagem do usuário e devolve a resposta final do agente.
        Executa internamente quantos ciclos de ferramentas forem necessários
        (limitado por settings.max_tool_rounds).
        """
        self._append("user", user_message)
        messages = [{"role": "system", "content": self.system_prompt}, *self.history]

        for _ in range(self.settings.max_tool_rounds):
            response = self.client.chat.completions.create(
                model=self.settings.model,
                messages=messages,
                tools=TOOL_SCHEMAS,
                tool_choice="auto",
                temperature=self.settings.temperature,
            )
            message = response.choices[0].message

            # Caso 1: o modelo pediu ferramenta(s) -> executa e devolve os resultados
            if message.tool_calls:
                messages.append(
                    {
                        "role": "assistant",
                        "content": message.content,
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments,
                                },
                            }
                            for tc in message.tool_calls
                        ],
                    }
                )
                for tc in message.tool_calls:
                    result = self.executor.execute(tc.function.name, tc.function.arguments)
                    self._log_tool(tc.function.name, tc.function.arguments, result)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": result,
                        }
                    )
                continue  # volta ao LLM com os resultados das ferramentas

            # Caso 2: resposta final em texto
            answer = message.content or "Desculpe, não consegui processar sua mensagem."
            self._append("assistant", answer)
            self._save_session()
            return answer

        # Limite de ciclos atingido: responde com degradação elegante
        fallback = (
            "Poxa, tive um problema para consultar os dados agora. Você pode repetir a "
            "pergunta em instantes? Se preferir, nossa equipe humana atende pelo "
            "(67) 3341-4444 ou contato@emporiodamusica.com.br."
        )
        self._append("assistant", fallback)
        self._save_session()
        return fallback

    # --------------------------------------------------------- rastreabilidade
    def stream_events(self, user_message: str) -> Generator[dict, None, str]:
        """
        Variante de `reply` que emite eventos ("tool", "answer") para a CLI
        exibir o que o agente está consultando em tempo real.
        Retorna a resposta final ao final do gerador.
        """
        self._append("user", user_message)
        messages = [{"role": "system", "content": self.system_prompt}, *self.history]

        for _ in range(self.settings.max_tool_rounds):
            response = self.client.chat.completions.create(
                model=self.settings.model,
                messages=messages,
                tools=TOOL_SCHEMAS,
                tool_choice="auto",
                temperature=self.settings.temperature,
            )
            message = response.choices[0].message

            if message.tool_calls:
                messages.append(
                    {
                        "role": "assistant",
                        "content": message.content,
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments,
                                },
                            }
                            for tc in message.tool_calls
                        ],
                    }
                )
                for tc in message.tool_calls:
                    result = self.executor.execute(tc.function.name, tc.function.arguments)
                    self._log_tool(tc.function.name, tc.function.arguments, result)
                    yield {
                        "type": "tool",
                        "name": tc.function.name,
                        "args": tc.function.arguments,
                        "result": result,
                    }
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
                continue

            answer = message.content or "Desculpe, não consegui processar sua mensagem."
            self._append("assistant", answer)
            self._save_session()
            return answer

        fallback = (
            "Poxa, tive um problema para consultar os dados agora. Você pode repetir a "
            "pergunta em instantes? Se preferir, nossa equipe humana atende pelo "
            "(67) 3341-4444 ou contato@emporiodamusica.com.br."
        )
        self._append("assistant", fallback)
        self._save_session()
        return fallback

    # ------------------------------------------------------------- histórico
    def _append(self, role: str, content: str) -> None:
        self.history.append({"role": role, "content": content})
        self._session_log.append({"ts": time.time(), "role": role, "content": content})
        self._prune_history()

    def _prune_history(self) -> None:
        """
        Mantém o histórico dentro do limite configurado.
        O system prompt não fica no histórico (é injetado a cada chamada),
        então a poda descrita aqui afeta apenas as mensagens da conversa.
        """
        limit = self.settings.history_max_messages
        if len(self.history) > limit:
            # Descarta os pares mais antigos, preservando o par mais recente intacto
            self.history = self.history[-limit:]

    def _log_tool(self, name: str, arguments: str, result: str) -> None:
        self._session_log.append(
            {"ts": time.time(), "role": "tool", "tool": name, "arguments": arguments,
             "result": result[:2000]}
        )

    def _save_session(self) -> None:
        """Grava a sessão em JSON local (auditoria do atendimento). Falhas são silenciosas."""
        try:
            sessions_dir = PROJECT_ROOT / ".sessions"
            sessions_dir.mkdir(exist_ok=True)
            path = sessions_dir / f"sessao_{time.strftime('%Y%m%d')}.jsonl"
            with path.open("a", encoding="utf-8") as f:
                for entry in self._session_log:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            self._session_log.clear()
        except Exception:
            pass


def create_agent(settings: Settings | None = None) -> AssistenteEmporio:
    """Fábrica do agente, carregando dados, políticas e retrieval."""
    return AssistenteEmporio(settings=settings or get_settings())

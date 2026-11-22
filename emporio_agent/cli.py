"""
CLI interativa do agente de atendimento da Empório da Música.

Execução:
    python -m emporio_agent               # chat interativo
    python -m emporio_agent --demo FILE   # modo demo: processa mensagens de um arquivo
                                          # (uma mensagem por linha) e imprime a conversa
"""
from __future__ import annotations

import argparse
import contextlib
import sys
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from .agent import create_agent
from .persona import STORE_NAME, STORE_SLOGAN

# Terminais Windows com codepage antiga (ex.: cp850/cp1252 no PyCharm) podem não
# representar caracteres de desenho/emoji; degradamos para "?" em vez de quebrar.
for _stream in (sys.stdout, sys.stderr):
    with contextlib.suppress(AttributeError, ValueError):  # stream sem reconfigure
        _stream.reconfigure(errors="replace")

console = Console()


def _regua() -> None:
    """Separador que degrada para ASCII se o terminal não suportar '─'."""
    try:
        "─".encode(sys.stdout.encoding or "ascii")
    except (LookupError, UnicodeEncodeError):
        console.print("[dim]" + "-" * console.width + "[/dim]")
        return
    console.rule(style="dim")


BANNER = f"""
[bold magenta]{STORE_NAME}[/bold magenta] — Atendimento Virtual
[dim]{STORE_SLOGAN}[/dim]
"""

HELP_TEXT = """[bold]Comandos:[/bold]
  [cyan]/sair[/cyan]   — encerra a conversa
  [cyan]/limpar[/cyan] — limpa a tela
  [cyan]/ajuda[/cyan]  — mostra esta ajuda"""


def _run_interactive() -> None:
    """Loop principal do chat interativo."""
    console.print(BANNER)
    console.print("[dim]Pergunte sobre produtos, preços, pedidos, políticas da loja…[/dim]\n")

    try:
        agent = create_agent()
    except Exception as exc:  # falha de configuração (ex.: sem API key)
        console.print(f"[red]Erro ao iniciar o agente:[/red] {exc}")
        console.print("[dim]Verifique o arquivo .env (veja .env.example).[/dim]")
        sys.exit(1)

    console.print(
        f'[green]Assistente:[/green] Olá! Bem-vindo à {STORE_NAME}, como posso ajudar?'
    )
    console.print(HELP_TEXT)
    _regua()

    while True:
        try:
            user_input = console.input("\n[bold cyan]Você:[/bold cyan] ").strip()
        except (KeyboardInterrupt, EOFError):
            user_input = "/sair"

        if not user_input:
            continue
        if user_input.lower() == "/sair":
            console.print(
                f"\n[green]Assistente:[/green] Obrigado por falar com a {STORE_NAME}. "
                "Sua música começa aqui — até logo!"
            )
            break
        if user_input.lower() == "/limpar":
            console.clear()
            continue
        if user_input.lower() == "/ajuda":
            console.print(HELP_TEXT)
            continue

        try:
            with console.status("[dim]consultando…[/dim]", spinner="dots"):
                for event in agent.stream_events(user_input):
                    if event["type"] == "tool":
                        console.print(
                            f'  [dim]→ consultando {event["name"]}…[/dim]'
                        )
                answer = agent.history[-1]["content"]
        except Exception as exc:
            console.print(f"[red]Erro ao processar a mensagem:[/red] {exc}")
            console.print("[dim]Verifique sua conexão e a configuração do provedor (.env).[/dim]")
            continue

        console.print("\n[green]Assistente:[/green]")
        console.print(Panel(Markdown(answer), border_style="green", padding=(0, 1)))


def _run_demo(demo_file: Path) -> None:
    """
    Modo demo: lê um arquivo com uma mensagem do cliente por linha e imprime
    a conversa completa (cliente e assistente). Usado para reproduzir as
    conversas de exemplo do diretório examples/ de forma determinística.
    """
    lines = [
        line.strip()
        for line in demo_file.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    if not lines:
        console.print(f"[red]Arquivo demo vazio:[/red] {demo_file}")
        sys.exit(1)

    agent = create_agent()
    console.print(f"[bold]Conversa demo[/bold] — {demo_file}\n")
    for message in lines:
        console.print(f"[bold cyan]Cliente:[/bold cyan] {message}\n")
        try:
            for event in agent.stream_events(message):
                if event["type"] == "tool":
                    console.print(f'  [dim]({event["name"]})[/dim]')
            answer = agent.history[-1]["content"]
        except Exception as exc:
            answer = f"[erro: {exc}]"
        console.print(f"[bold green]Assistente:[/bold green] {answer}\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="emporio_agent",
        description="Agente de atendimento da Empório da Música (chat no terminal)",
    )
    parser.add_argument(
        "--demo",
        type=Path,
        metavar="ARQUIVO",
        help="executa uma conversa a partir de um arquivo de mensagens (1 por linha)",
    )
    args = parser.parse_args()

    if args.demo:
        _run_demo(args.demo)
    else:
        _run_interactive()


if __name__ == "__main__":
    main()

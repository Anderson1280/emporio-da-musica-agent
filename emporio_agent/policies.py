"""
Extração e fragmentação do Manual de Políticas (PDF).

O PDF é dividido em blocos (chunks) por seção numerada do manual
("1. Sobre a Empório da Música", "4.1 Direito de Arrependimento", ...).
Fragmentar por seção — e não por tamanho fixo — mantém cada chunk
semanticamente completo, o que melhora muito a qualidade do retrieval.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from pypdf import PdfReader


@dataclass
class PolicyChunk:
    """Um trecho do manual, com metadados para rastreabilidade."""

    chunk_id: str
    section: str          # título da seção, ex.: "4.1 Direito de Arrependimento"
    page: int             # página do PDF onde a seção começa
    content: str          # texto completo da seção

    def as_text(self) -> str:
        """Representação textual usada para indexação e para o prompt do LLM."""
        return f"[{self.section}] (página {self.page})\n{self.content}"


_HEADING_RE = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+(.*)$")
_MAX_TITLE_LEN = 60  # títulos do manual têm no máximo ~55 caracteres


def _extract_pdf_text(pdf_path) -> list[str]:
    """Extrai o texto de cada página do PDF, preservando a ordem."""
    reader = PdfReader(str(pdf_path))
    return [page.extract_text() or "" for page in reader.pages]


def _split_sections(pages: list[str]) -> list[tuple[str, int, list[str]]]:
    """
    Percorre o texto e agrupa linhas por seção numerada do manual
    (ex.: "1. Sobre a Empório da Música", "4.1 Direito de Arrependimento").

    O pypdf às vezes cola o título com o primeiro bullet na MESMA linha
    ("4.1 Direito de Arrependimento (Compras Online) • O cliente pode..."),
    então quando a linha numerada contém " • " separa-se o título do
    conteúdo. Itens de lista numerados ("1. Saudação: cumprimentar o
    cliente...") são linhas longas sem bullet: permanecem como conteúdo da
    seção à qual pertencem, sem fragmentar o índice.
    """
    sections: list[tuple[str, int, list[str]]] = []
    current_title, current_page, current_lines = "Capa e Dados Gerais da Loja", 1, []

    for page_number, page_text in enumerate(pages, start=1):
        for raw_line in page_text.splitlines():
            line = re.sub(r"\s+", " ", raw_line.strip())  # normaliza espaços múltiplos do PDF
            if not line or line.startswith(("Empório da Música Manual", "Página ")):
                continue  # remove cabeçalho/rodapé repetidos

            match = _HEADING_RE.match(line)
            if match:
                number, rest = match.group(1), match.group(2).strip()
                if " • " in rest:
                    title_part, content_part = rest.split(" • ", 1)
                    if len(title_part.strip()) <= _MAX_TITLE_LEN:
                        _open_section(sections, current_title, current_page, current_lines)
                        current_title = f"{number} {title_part.strip().rstrip('. ')}".strip()
                        current_page = page_number
                        current_lines = [f"• {content_part.strip()}"]
                        continue
                elif len(rest) <= _MAX_TITLE_LEN and not rest.endswith("."):
                    _open_section(sections, current_title, current_page, current_lines)
                    current_title = f"{number} {rest.rstrip('. ')}".strip()
                    current_page = page_number
                    current_lines = []
                    continue
                # caso contrário: item de lista numerada -> conteúdo comum

            current_lines.append(line)

    _open_section(sections, current_title, current_page, current_lines)
    return sections


def _open_section(
    sections: list[tuple[str, int, list[str]]],
    title: str,
    page: int,
    lines: list[str],
) -> None:
    """Fecha a seção corrente, guardando-a se tiver conteúdo útil."""
    if lines:
        sections.append((title, page, lines))


def load_policy_chunks(pdf_path) -> list[PolicyChunk]:
    """Carrega o PDF e retorna os chunks por seção, prontos para indexação."""
    pages = _extract_pdf_text(pdf_path)
    chunks: list[PolicyChunk] = []

    for idx, (title, page, lines) in enumerate(_split_sections(pages)):
        content = "\n".join(lines).strip()
        if len(content) < 30:
            continue  # descarta seções triviais (apenas título)
        chunks.append(
            PolicyChunk(
                chunk_id=f"pol-{idx:03d}",
                section=title[:120],
                page=page,
                content=content,
            )
        )
    return chunks

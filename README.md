# Empório da Música — Agente de Atendimento

**Desafio Técnico — AI Engineer (Artefact, 2026) · Protótipo de agente de atendimento por mensagens de texto**

> *Sua música começa aqui.* 🎸

O **Empório da Música** é uma loja de instrumentos musicais em Campo Grande/MS cuja equipe
está sobrecarregada por perguntas recorrentes (horários, status de pedidos, preços,
promoções, trocas). Este projeto entrega um **assistente virtual em Python** que atende
clientes por mensagem de texto, consultando **dados reais da operação** (CSVs) e o
**Manual de Políticas da loja** (PDF) antes de responder.

---

## Como rodar

### 1. Pré-requisitos

- Python **3.10+**
- Uma chave de API da OpenAI (o modelo padrão é `gpt-4o-mini`)

### 2. Instalação

```bash
# Clone o repositório e entre na pasta
git clone https://github.com/<seu-usuario>/emporio-da-musica-agent.git
cd emporio-da-musica-agent

# Crie e ative um ambiente virtual
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows

# Instale as dependências
pip install -r requirements.txt
```

> **Nota sobre versões:** as faixas do `requirements.txt` são
> deliberadamente conservadoras (ex.: `numpy<2.3`). Versões recém-lançadas
> quebraram em Windows recém-configurado — numpy 2.5.x falha ao carregar a
> DLL C (`ImportError: DLL load failed ... _multiarray_umath`) e rich 15
> removeu parâmetros antigos. Os limites superiores garantem um conjunto
> maduro e testado em qualquer máquina.

### 3. Configuração do ambiente

```bash
cp .env.example .env
```

Abra o `.env` e informe sua chave:

```ini
OPENAI_API_KEY=sk-sua-chave-aqui
# Opcional:
# OPENAI_MODEL=gpt-4o-mini
# OPENAI_BASE_URL=https://api.openai.com/v1   (mude para testar outros endpoints compatíveis)
```

O `OPENAI_BASE_URL` segue o padrão OpenAI, então **qualquer endpoint compatível** funciona
(OpenAI oficial, Azure OpenAI, provedores locais como Ollama com camada de compatibilidade
etc.) sem mudar uma linha de código.

### 4. Rodando o chat

```bash
python -m emporio_agent
```

Você verá o chat no terminal:

```
Empório da Música — Atendimento Virtual
Sua música começa aqui.

Você: Quais opções de violões disponíveis custando até R$1000?
  → consultando buscar_produtos…
Assistente: Olá! Tenho várias opções até R$ 1000:
- Tagima Memphis AC-39 Nylon Natural — R$ 429,90
  ...
```

Comandos do chat: `/ajuda`, `/limpar` e `/sair`.

### 5. Rodando as conversas de exemplo

Os cenários das conversas em [`examples/`](examples/) podem ser reproduzidos:

```bash
python -m emporio_agent --demo examples/demo_messages/03_status_pedido.txt
```

### 6. Testes

```bash
pytest tests/ -v
```

Todos os testes rodam **offline** (nenhuma chamada de LLM real: a camada de dados, o
retrieval e o loop de ferramentas são testados com LLM simulado), então o CI é estável.

---

## Arquitetura da solução

```
                      ┌────────────────────────────┐
  mensagem do         │  CLI (rich)                │
  cliente ──────────▶ │  chat no terminal          │
                      └─────────────┬──────────────┘
                                    │
                      ┌─────────────▼──────────────┐
                      │  Agente (agent.py)         │      ┌─────────────────────┐
                      │  loop de function calling  │◀────▶│  LLM (gpt-4o-mini   │
                      │  + histórico da conversa   │      │  via SDK OpenAI)    │
                      └──┬──────────┬──────────────┘      └─────────────────────┘
                         │          │
        ferramentas de   │          │   ferramenta de
        dados (determin.)│          │   políticas (RAG)
                         ▼          ▼
      ┌──────────────────────┐   ┌──────────────────────────┐
      │ data_store.py        │   │ retrieval.py (híbrido)   │
      │ pandas sobre os CSVs │   │ BM25 + embeddings (RRF)  │
      │ produtos/pedidos/... │   │ policies.py (PDF→chunks) │
      └──────────────────────┘   └──────────────────────────┘
```

**Fluxo de uma mensagem:** o system prompt fixa a persona e as regras; o LLM decide
sozinho quando chamar ferramentas; o agente executa e devolve os resultados ao LLM
(até 5 ciclos); a resposta final sai em formato de mensagem de WhatsApp.

### Estrutura do projeto

```
emporio-da-musica-agent/
├── emporio_agent/           # código do agente
│   ├── agent.py             # loop de function calling + histórico
│   ├── cli.py               # interface interativa (rich) + modo --demo
│   ├── config.py            # configurações via .env
│   ├── data_store.py        # carga/normalização/consulta dos CSVs (pandas)
│   ├── persona.py           # persona e regras de atendimento (system prompt)
│   ├── policies.py          # extração e chunking do Manual de Políticas (PDF)
│   ├── retrieval.py         # retrieval híbrido: BM25 + embeddings (RRF)
│   └── tools.py             # esquemas das ferramentas + executor
├── data/                    # dados fornecidos pela loja (CSVs + políticas PDF)
├── examples/                # 5 conversas reais capturadas (.md)
│   └── demo_messages/       # mensagens dos cenários (reproduzíveis)
├── tests/                   # suíte pytest (offline)
├── .github/workflows/ci.yml # lint + testes a cada push/PR
├── requirements.txt
├── pyproject.toml           # configuração do ruff e do pytest
└── .env.example
```

---

## Decisões técnicas (e por quê)

### 1. Arquitetura híbrida: function calling para dados + RAG para políticas

O problema tem **dois tipos de conhecimento com naturezas diferentes**:

| Tipo | Exemplo | Característica | Solução |
|---|---|---|---|
| Operacional, estruturado | "Quanto custa o Takamine GD20?", "Cadê meu pedido 8?" | Resposta **exata** e **mutável** (estoque muda, pedido anda) | Ferramentas Python determinísticas sobre os CSVs |
| Normativo, textual | "Posso devolver?", "Qual a garantia?" | Resposta **semântica**, em linguagem natural, volume pequeno | RAG sobre o PDF do manual |

Dados de preço/estoque **nunca deveriam passar por similaridade semântica**: um erro de
centavos ou de unidade vira propaganda enganosa (o próprio manual da loja alerta para
isso na seção 7.1). Por outro lado, perguntas de política são formuladas de infinitas
maneiras — é exatamente o caso de uso do RAG. Forçar um único mecanismo para os dois
mundos degradaria um dos lados; a combinação é o melhor dos dois.

### 2. Function calling nativo (sem framework de agentes)

Usei o **SDK oficial da OpenAI com tool calling nativo**, sem LangChain/LlamaIndex:

- **Transparência**: o núcleo do loop do agente cabe em ~80 linhas legíveis
  (`agent.py`), fáceis de auditar e depurar — importante num processo seletivo.
- **Custo de dependências**: frameworks trazem abstrações que mudam rápido; o tool
  calling nativo é estável e é tudo que este caso precisa.
- **Precisão**: o roteamento de ferramenta fica a cargo do próprio modelo treinado para
  isso, em vez de prompts manuais de ReAct ("pensar passo a passo e escrever AÇÃO:").
- O limite de ciclos (`MAX_TOOL_ROUNDS=5`) evita loops infinitos e a resposta de
  fallback direciona para a equipe humana.

### 3. Retrieval híbrido das políticas: BM25 + embeddings com RRF

O PDF é fragmentado **por seção numerada do manual** (`policies.py`) — e não por janela
de tamanho fixo — porque cada seção é uma regra semanticamente completa ("4.1 Direito de
Arrependimento", "3.1 Regras de Parcelamento"). Isso preserva prazos e condições juntos
no mesmo chunk, o que é crítico para respostas corretas.

Sobre os chunks rodam **duas estratégias combinadas**:

- **BM25 léxico** (implementação própria, ~40 linhas): determinístico, custo zero,
  offline. Três reforços léxicos para o português: (a) truncamento de termos por
  radical de 5 e 4 caracteres — o de 4 cobre flexões irregulares em que a consoante
  muda ("devolver"/"devolução" compartilham a raiz "devo"); (b) **expansão de
  consulta**, um pequeno mapa de sinônimos que liga o vocabulário do cliente ao
  vocabulário do manual ("frete" → "entrega", "reembolso" → "estorno"); (c) **field
  boost** simplificado (estilo BM25F): termos do título da seção e do breadcrumb da
  seção-pai recebem peso maior que o corpo do texto.
- **Embeddings** (`text-embedding-3-small`): capturam paráfrase que o léxico perde
  ("cadê meu pedido" ↔ "rastreamento"). Com cache em disco (`.cache/`) para não
  recomputar.

Os dois rankings são fundidos por **Reciprocal Rank Fusion** (k=60), robusto a escalas
diferentes. **Degradação graciosa**: sem chave de embedding ou sem rede, o sistema cai
automaticamente para BM25 puro — o agente segue funcionando em qualquer ambiente.

### 4. Modelo: gpt-4o-mini

- **Custo-benefício**: centavos por sessão de atendimento, com tool calling confiável —
  o requisito central desta arquitetura.
- **Roteabilidade**: todo acesso passa pela interface compatível com OpenAI; trocar de
  modelo/provedor é mudar variáveis no `.env` (inclusive endpoints locais).
- Temperatura baixa (`0.3`): atendimento é tarefa de fidelidade a fatos, não de criação.

### 5. Interface: CLI no terminal

O foco do desafio é o **agente funcionando corretamente**, e a CLI é o caminho mais
direto para demonstrar isso (zero infraestrutura extra, ideal para o avaliador rodar em
1 minuto). A implementação isola a conversa em `agent.py`, de modo que um canal real
(WhatsApp Business API, por exemplo) seria apenas outro "adapter" chamando o mesmo
`agent.reply()`. O modo `--demo` também serve como contrato de integração: recebe
mensagens de um arquivo e produz as respostas — um passo natural para testes E2E ou
webhook.

### 6. Persistência do histórico

- **Em memória, por sessão**: no canal de texto, a conversa é contínua dentro da sessão;
  o histórico recente basta para resolver anáforas ("e dele?", "quanto fica no PIX?").
- **Poda automática** (`HISTORY_MAX_MESSAGES=24`): mantém o custo e a janela de contexto
  sob controle em conversas longas.
- **Log de sessão em JSONL** (`.sessions/`, fora do git): cada turno e cada chamada de
  ferramenta ficam registrados com timestamp — rastreabilidade que uma loja real
  precisaria para auditoria e melhoria contínua.
- **Persistência cross-session** (retomar conversa por telefone) teria sentido numa
  integração com WhatsApp, onde o remetente é identificado; na CLI anônima seria
  artificial. Ficou registrado como evolução futura.

### 7. Tratamento dos dados

- **Normalização no carregamento** (`data_store.py`): tipos numéricos, datas, junção
  pedido↔itens↔produtos, mapeamento de status/formas de pagamento para português
  amigável ("shipped" → "enviado (em trânsito)").
- **Promoções**: apenas `is_active=1` entram no preço final; o preço promocional é
  sempre apresentado com o original e o percentual (transparência exigida pela política
  6.2). O desconto de PIX (5%) nunca é cumulativo — regra refletida no prompt.
- **Busca tolerante**: termos sem acento encontram produtos com acento ("violao" ↔
  "violão"), por normalização Unicode.
- **Proteção de dados (LGPD)**: a ferramenta de pedidos só devolve dados quando o cliente
  informa o número do pedido e/ou o telefone cadastrado; telefone que não bate com o
  cadastro do pedido não vaza informação (coberto por teste).
- Os CSVs foram mantidos no repo com nomes simplificados (`products.csv` etc.); os nomes
  originais vinham com o prefixo `desafio_tecnico_ai_eng - `.

### 8. Estratégia de prompt

O system prompt (`persona.py`) é construído **a partir do próprio Manual de Políticas**
(seção 7 — Atendimento via WhatsApp): tom "informal mas profissional, como um amigo que
entende de música", saudação pelo nome quando possível, escopo exclusivo de instrumentos
com redirecionamento educado de acessórios, e a regra mais importante do manual —
**nunca informar preço, estoque ou prazo sem consultar o sistema**. Além disso:

- Gatilhos obrigatórios de `buscar_politicas` (garantia, troca, frete, parcelamento…),
  evitando que o modelo responda prazos "de memória";
- Data corrente injetada no prompt, para calcular prazos ("recebi anteontem, posso
  devolver?") contra as regras dos 7/30/90 dias;
- Formato de mensagem de WhatsApp: texto curto, sem markdown pesado;
- Honestidade obrigatória: sem a informação, dizer que não encontrou e passar o contato
  humano — nunca inventar.

---

## Limitações conhecidas (e o que faria com mais tempo)

1. **Sem escrita no banco**: o agente é read-only (por design, num protótipo de
   atendimento). Com mais tempo: ferramentas de ação com confirmação explícita do
   cliente (agendar troca, registrar reclamação) e webhook para a equipe.
2. **RAG sem reranking neural**: BM25+RRF cobre bem um manual de 8 páginas; para um
   catálogo/FAQ grande, adicionaria reranking cross-encoder e avaliação sistemática
   (golden set de perguntas com resposta esperada, métrica de recall@k).
3. **Identidade do cliente por telefone é fraca**: uma camada de verificação (código
   enviado ao número cadastrado) seria obrigatória antes de expor qualquer dado.
4. **Sem testes end-to-end com LLM real**: a suíte usa LLM simulado para ser estável e
   gratuita; com mais tempo, testes E2E com asserções semânticas (LLM-as-judge) num
   job noturno.
5. **Cobertura de segurança de prompt**: não há sanitização contra prompt injection
   vindo do cliente (ex.: "ignore suas instruções"). Mitigação parcial: respostas só
   com dados das ferramentas. Com mais tempo: validação de entrada e camada de filtro.
6. **Observabilidade mínima**: o log JSONL serve para auditoria, mas uma integração com
   traces (ex.: OpenTelemetry/Langfuse) mediria latência, custo e taxas de uso de
   ferramenta por sessão.
7. **Concurrent**: a CLI atende um cliente por processo; um serviço real precisaria de
   gestão de sessões concorrentes (a API já isola isso naturalmente por requisição).

---

## Uso de assistentes de código

Este projeto foi desenvolvido com auxílio de **Z.ai (GLM)** como assistente de código,
com o seguinte workflow:

1. **Arquitetura e decisões**: as escolhas (híbrido function calling + RAG, BM25+RRF,
   CLI) foram definidas por mim e a IA atuou como revisor crítico dos trade-offs.
2. **Geração de código**: módulos foram escritos em iterações curtas de prompt → código
   gerado → revisão manual linha a linha → ajustes. Todos os arquivos foram lidos,
   corrigidos e testados por mim; o design e as justificativas são meus.
3. **Testes**: suíte pytest escrita com apoio da IA e validada pela correção real de
   bugs que ela revelou (desalinhamento de índice no pandas, chunking do PDF).
4. **Conversas de exemplo**: capturadas **executando o agente real** deste repositório
   sobre os cenários de `examples/demo_messages/`. Como a chave OpenAI não estava
   disponível no ambiente de captura, o agente rodou sobre um endpoint compatível com a
   API OpenAI (LLM GLM) — mesmo código, mesmas ferramentas, mesmo RAG. Com
   `gpt-4o-mini` o comportamento é equivalente, e qualquer conversa pode ser reproduzida
   com `python -m emporio_agent --demo examples/demo_messages/<arquivo>`.

---

## Checklist dos entregáveis

- [x] **Projeto Python** do agente de mensagens de texto (única restrição técnica)
- [x] **Persona** alinhada ao tom da loja (Manual de Políticas, seção 7.1)
- [x] Recebe e responde com base no **contexto disponibilizado** (CSVs + PDF)
- [x] Sabe **quando consultar dados** e **quando consultar políticas** (function calling
      com 5 ferramentas + RAG)
- [x] Trata **perguntas fora do escopo** (acessórios, assuntos aleatórios)
- [x] **README** com instruções, decisões justificadas e limitações
- [x] **3–5 exemplos de interação**, incluindo situações não triviais (03 e 04)
- [x] **Testes** (22 testes, offline) e **CI** (GitHub Actions)

# Local Agent

Agente local para desenvolvedores, escrito em Python. Ele conversa com um modelo servido por uma API compatível com OpenAI (por exemplo, LM Studio) e pode chamar ferramentas locais limitadas ao workspace configurado.

## Estado atual

O projeto está em desenvolvimento inicial. O agente oferece um loop de tool calling e quatro ferramentas: calculadora aritmética, data/hora local, listagem de diretório e leitura de arquivo de texto UTF-8. A conversa não é persistida entre entradas.

As ferramentas de arquivos aceitam somente caminhos relativos ao workspace e rejeitam `..`, caminhos absolutos e destinos resolvidos fora do workspace. A leitura tem limite de tamanho. O agente ainda não grava arquivos nem executa comandos.

## Estrutura

- `agent/core`: orquestração da conversa e chamadas de ferramentas.
- `agent/llm`: cliente do endpoint compatível com OpenAI.
- `agent/tools`: contratos, validação, registro e implementações das ferramentas.
- `tests/unit`: testes das funcionalidades existentes.

## Requisitos e configuração

Use Python 3.10 ou superior. Crie um ambiente virtual e instale as dependências:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Copie `.env.example` para `.env` e ajuste os valores. Inicie o servidor local, carregue o modelo e configure `LLM_MODEL` com o identificador informado pelo servidor. A chave pode ser um valor local fictício se o servidor não exigir autenticação. Nunca versione `.env` ou credenciais reais.

| Variável | Padrão | Descrição |
| --- | --- | --- |
| `LLM_BASE_URL` | `http://localhost:1234/v1` | URL base da API compatível com OpenAI. |
| `LLM_API_KEY` | `lm-studio` | Chave aceita pelo servidor local; use a fornecida pelo servidor se necessária. |
| `LLM_MODEL` | (obrigatório) | Identificador do modelo carregado. |
| `LLM_TIMEOUT_SECONDS` | `120` | Tempo limite da requisição ao modelo. |
| `LLM_TEMPERATURE` | `0.2` | Temperatura enviada na chamada de chat. |
| `LOCAL_AGENT_WORKSPACE` | `.` (raiz do projeto) | Raiz permitida para ferramentas de arquivos. Caminhos relativos são resolvidos a partir da raiz do projeto. |
| `LOCAL_AGENT_MAX_FILE_BYTES` | `100000` | Tamanho máximo de arquivo que a ferramenta pode ler. |
| `LOCAL_AGENT_MAX_ITERATIONS` | `10` | Máximo de ciclos de resposta/chamadas de ferramenta por entrada. |
| `LOCAL_AGENT_LOG_LEVEL` | `WARNING` | Nível de log (`DEBUG`, `INFO`, `WARNING` ou `ERROR`). |

As variáveis numéricas devem conter números válidos; `LOCAL_AGENT_MAX_FILE_BYTES` precisa ser maior que zero.

## Uso

Com o servidor local ativo e o modelo carregado:

```powershell
python main.py
```

Digite `sair` para encerrar. Os logs são enviados ao console conforme `LOCAL_AGENT_LOG_LEVEL`.

## Segurança e escopo

A calculadora interpreta uma lista restrita de operações aritméticas por meio de uma árvore sintática; não executa Python arbitrário. A leitura de arquivos é somente leitura, limitada ao workspace, a UTF-8 e ao tamanho configurado. Links simbólicos cujo destino fique fora do workspace são rejeitados.

Escrita de arquivos e execução de comandos não estão implementadas. Se forem adicionadas no futuro, devem ter escopo explícito e pedir confirmação do usuário antes de alterar o projeto ou iniciar processos.

## Testes

```powershell
python -m pytest
```

# Local Agent

Agente local para desenvolvedores, escrito em Python. Ele conversa com um modelo servido por uma API compatível com OpenAI (por exemplo, LM Studio) e pode chamar ferramentas locais limitadas ao workspace configurado.

## Estado atual

O projeto está em desenvolvimento inicial. O agente oferece um loop de tool calling e ferramentas para cálculos, data/hora local, listagem e busca de arquivos, leitura de arquivos por trechos, consulta a PostgreSQL e movimentação/renomeação de itens do workspace. A conversa não é persistida entre entradas.

As ferramentas de arquivos aceitam somente caminhos relativos ao workspace e rejeitam `..`, caminhos absolutos e destinos resolvidos fora do workspace. A leitura e a busca têm limites de tamanho/resultado. O agente pode mover/renomear itens após confirmação; ainda não edita conteúdo nem executa comandos.

A ferramenta PostgreSQL conecta-se ao servidor indicado em `POSTGRES_DSN`, que pode estar em outro computador — por exemplo, no PC que hospeda o LM Studio. Ela aceita uma única consulta `SELECT`/`WITH` dentro de uma transação read-only, com timeout e limite de linhas. Configure um usuário PostgreSQL dedicado com permissões apenas de leitura; a transação read-only é uma proteção adicional, não substitui privilégios mínimos.

A ferramenta `move_path` pode mover ou renomear arquivos e diretórios dentro do workspace. No terminal, o agente mostra origem e destino e exige que o usuário digite `s` para confirmar. Destinos existentes, links simbólicos e caminhos fora do workspace são recusados. A ferramenta não copia nem exclui itens.

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
| `LOCAL_AGENT_MAX_SEARCH_BYTES` | `5000000` | Máximo de bytes lidos em uma busca no workspace. |
| `LOCAL_AGENT_MAX_ITERATIONS` | `10` | Máximo de ciclos de resposta/chamadas de ferramenta por entrada. |
| `LOCAL_AGENT_LOG_LEVEL` | `WARNING` | Nível de log (`DEBUG`, `INFO`, `WARNING` ou `ERROR`). |
| `POSTGRES_DSN` | (vazio; integração desativada) | URI de conexão PostgreSQL, por exemplo `postgresql://usuario:senha@host:5432/banco`. Use o endereço/IP acessível do PC do banco. |
| `POSTGRES_CONNECT_TIMEOUT_SECONDS` | `5` | Tempo máximo para estabelecer conexão. |
| `POSTGRES_STATEMENT_TIMEOUT_MS` | `5000` | Tempo máximo de execução de cada consulta. |
| `POSTGRES_MAX_ROWS` | `100` | Máximo de linhas retornadas, entre 1 e 500. |

As variáveis numéricas devem conter números válidos; `LOCAL_AGENT_MAX_FILE_BYTES` precisa ser maior que zero. O PostgreSQL permanece desativado se `POSTGRES_DSN` estiver vazio.

## Uso

Com o servidor local ativo e o modelo carregado:

```powershell
python main.py
```

Digite `sair` para encerrar. Os logs são enviados ao console conforme `LOCAL_AGENT_LOG_LEVEL`.

## Segurança e escopo

A calculadora interpreta uma lista restrita de operações aritméticas por meio de uma árvore sintática; não executa Python arbitrário. A leitura e busca de arquivos são somente leitura, limitadas ao workspace e ao tamanho/quantidade configurados. Links simbólicos cujo destino fique fora do workspace são rejeitados. O agente não abre portas no computador do banco: ele inicia uma conexão de saída ao host e à porta informados no DSN. O servidor PostgreSQL precisa aceitar conexões desse host, com regras de rede e autenticação apropriadas.

Edição do conteúdo de arquivos e execução de comandos não estão implementadas. Se forem adicionadas no futuro, devem ter escopo explícito e pedir confirmação do usuário antes de alterar o projeto ou iniciar processos.

## Testes

```powershell
python -m pytest
```

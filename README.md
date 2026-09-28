# Local Agent

Agente local para desenvolvedores, escrito em Python. Ele conversa com um modelo servido por uma API compatível com OpenAI (por exemplo, LM Studio) e pode chamar ferramentas locais limitadas ao workspace configurado.

## Estado atual

O projeto está em desenvolvimento inicial. O agente oferece um loop de tool calling e ferramentas para cálculos, data/hora local, arquivos, PostgreSQL, busca na web e leitura controlada de páginas públicas. As conversas são persistidas localmente em SQLite e a mais recente é retomada ao iniciar o agente. O histórico é separado por workspace, e a busca em conversas fica restrita ao projeto ativo. Quando solicitado, o agente também pode buscar trechos em conversas salvas. O diretório padrão é `%LOCALAPPDATA%\LocalAgent` no Windows; configure `LOCAL_AGENT_DATA_DIR` para escolher outro local. Históricos longos recebem um resumo persistente para reduzir o contexto enviado ao modelo, preservando as mensagens originais. O arquivo contém mensagens e resultados de ferramentas em texto legível; proteja-o como qualquer dado pessoal ou código privado.

As ferramentas de arquivos aceitam somente caminhos relativos ao workspace e rejeitam `..`, caminhos absolutos e destinos resolvidos fora do workspace. A leitura, busca e edição têm limites. O agente pode editar trechos após apresentar um diff e receber confirmação, mover/renomear itens após confirmação e executar uma lista restrita de comandos de desenvolvimento após mostrar o comando e receber confirmação.

A ferramenta PostgreSQL conecta-se ao servidor indicado em `POSTGRES_DSN`, que pode estar em outro computador — por exemplo, no PC que hospeda o LM Studio. Ela aceita uma única consulta `SELECT`/`WITH` dentro de uma transação read-only, com timeout e limite de linhas. Configure um usuário PostgreSQL dedicado com permissões apenas de leitura; a transação read-only é uma proteção adicional, não substitui privilégios mínimos.

A ferramenta `move_path` pode mover ou renomear arquivos e diretórios dentro do workspace. No terminal, o agente mostra origem e destino e exige que o usuário digite `s` para confirmar. Destinos existentes, links simbólicos e caminhos fora do workspace são recusados. A ferramenta não copia nem exclui itens.

## Estrutura

- `main.py`: interface de terminal e seleção da conversa ativa.
- `agent/core`: orquestração da conversa e chamadas de ferramentas.
- `agent/llm`: cliente do endpoint compatível com OpenAI.
- `agent/tools`: contratos, validação, registro e implementações das ferramentas.
- `docs/uso.md`: instalação, configuração, comandos, ferramentas e privacidade do histórico.
- `docs/architecture/overview.md`: arquitetura, fluxo de execução e instruções para adicionar ferramentas.
- `tests/unit`: testes das funcionalidades existentes.

## Documentação

- [Guia de uso](docs/uso.md)
- [Visão da arquitetura](docs/architecture/overview.md)

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
| `BRAVE_SEARCH_API_KEY` | (vazio) | Chave opcional da Brave Search API; necessária para habilitar `search_web`. |
| `LOCAL_AGENT_WORKSPACE` | `.` (raiz do projeto) | Raiz permitida para ferramentas de arquivos. Caminhos relativos são resolvidos a partir da raiz do projeto. |
| `LOCAL_AGENT_DATA_DIR` | `%LOCALAPPDATA%\LocalAgent` no Windows | Diretório local para o banco SQLite do histórico. No Linux/macOS, usa `XDG_DATA_HOME/local-agent` ou `~/.local/share/local-agent`. |
| `LOCAL_AGENT_MAX_FILE_BYTES` | `100000` | Tamanho máximo de arquivo que a ferramenta pode ler. |
| `LOCAL_AGENT_MAX_SEARCH_BYTES` | `5000000` | Máximo de bytes lidos em uma busca no workspace. |
| `LOCAL_AGENT_MAX_ITERATIONS` | `10` | Máximo de ciclos de resposta/chamadas de ferramenta por entrada. |
| `LOCAL_AGENT_MAX_CONTEXT_CHARS` | `60000` | Limite aproximado do histórico enviado ao modelo; o histórico salvo continua completo. |
| `LOCAL_AGENT_LOG_LEVEL` | `WARNING` | Nível de log (`DEBUG`, `INFO`, `WARNING` ou `ERROR`). |
| `POSTGRES_DSN` | (vazio; integração desativada) | URI de conexão PostgreSQL, por exemplo `postgresql://usuario:senha@host:5432/banco`. Use o endereço/IP acessível do PC do banco. |
| `POSTGRES_CONNECT_TIMEOUT_SECONDS` | `5` | Tempo máximo para estabelecer conexão. |
| `POSTGRES_STATEMENT_TIMEOUT_MS` | `5000` | Tempo máximo de execução de cada consulta. |
| `POSTGRES_MAX_ROWS` | `100` | Máximo de linhas retornadas, entre 1 e 500. |

As variáveis numéricas devem conter números válidos; `LOCAL_AGENT_MAX_FILE_BYTES` precisa ser maior que zero. O PostgreSQL permanece desativado se `POSTGRES_DSN` estiver vazio.

Para habilitar a busca na web, configure `BRAVE_SEARCH_API_KEY` no `.env`. Consultas são enviadas à Brave Search API; páginas lidas são acessadas pelo computador local. O leitor aceita páginas públicas HTTP/HTTPS, bloqueia endereços locais/privados e limita redirecionamentos, bytes e texto retornado.

## Uso

Com o servidor local ativo e o modelo carregado:

```powershell
python main.py
```

Digite `sair` para encerrar. Os comandos `/nova`, `/conversas`, `/abrir ID`, `/limpar`, `/apagar ID` e `/apagar-tudo` gerenciam o histórico. A exclusão total pede confirmação. Os logs são enviados ao console conforme `LOCAL_AGENT_LOG_LEVEL`.

## Segurança e escopo

A calculadora interpreta uma lista restrita de operações aritméticas por meio de uma árvore sintática; não executa Python arbitrário. A leitura e busca de arquivos são somente leitura, limitadas ao workspace e ao tamanho/quantidade configurados. Edições exigem revisão de diff e confirmação, substituem uma ocorrência exata e recusam arquivos alterados desde a revisão. Comandos usam lista de argumentos sem shell e só permitem `python -m pytest`, `git status` e `git diff`; cada execução exige confirmação, roda no workspace e tem timeout e saída limitados. Links simbólicos cujo destino fique fora do workspace são rejeitados. O agente não abre portas no computador do banco: ele inicia uma conexão de saída ao host e à porta informados no DSN. O servidor PostgreSQL precisa aceitar conexões desse host, com regras de rede e autenticação apropriadas.

## Testes

```powershell
python -m pytest
```

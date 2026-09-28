# Guia de uso

Este guia cobre a execução do Local Agent, a configuração do modelo, as ferramentas disponíveis e o histórico local.

## O que o agente faz

O Local Agent é um programa de terminal para conversar com um modelo servido por uma API compatível com OpenAI. O padrão aponta para `http://localhost:1234/v1`, endereço comum do LM Studio, mas o endpoint pode ser substituído por outro servidor compatível.

O modelo pode solicitar ferramentas locais. O programa valida os argumentos, executa a ferramenta e devolve o resultado ao modelo para compor a resposta. O agente inclui ferramentas para cálculo, data e hora, navegação e leitura de arquivos, busca no workspace, consulta PostgreSQL e movimentação de arquivos com confirmação.

“Local” descreve a execução do programa e o endpoint padrão do modelo. Se você configurar outro endpoint LLM ou `POSTGRES_DSN` remoto, dados da conversa ou consultas também poderão ser enviados a esses serviços.

## Requisitos e instalação

- Python 3.10 ou superior.
- Um servidor de modelo ativo com API compatível com OpenAI.
- Opcionalmente, PostgreSQL acessível pela máquina que executa o agente.

No PowerShell, na raiz do projeto:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edite `.env` e preencha pelo menos `LLM_MODEL` com o identificador do modelo carregado no servidor. Depois, inicie o agente:

```powershell
python main.py
```

O servidor LLM deve estar ativo antes de enviar uma mensagem. Para encerrar, digite `sair`.

## Configuração

As configurações podem ser definidas no ambiente ou em `.env`. Nunca versione credenciais reais.

| Variável | Padrão | Finalidade |
| --- | --- | --- |
| `LLM_BASE_URL` | `http://localhost:1234/v1` | URL base do endpoint compatível com OpenAI. |
| `LLM_API_KEY` | `lm-studio` | Chave enviada ao endpoint; pode ser fictícia se o servidor não exigir autenticação. |
| `LLM_MODEL` | vazio | Identificador obrigatório do modelo servido. |
| `LLM_TIMEOUT_SECONDS` | `120` | Timeout da chamada ao modelo. |
| `LLM_TEMPERATURE` | `0.2` | Temperatura enviada ao modelo. |
| `BRAVE_SEARCH_API_KEY` | vazio | Chave da Brave Search API; necessária para pesquisar na web. |
| `LOCAL_AGENT_WORKSPACE` | `.` | Diretório permitido às ferramentas de arquivos. Caminhos relativos são resolvidos a partir da raiz do projeto. |
| `LOCAL_AGENT_DATA_DIR` | diretório de dados do usuário | Diretório onde será criado `history.sqlite3`. |
| `LOCAL_AGENT_MAX_FILE_BYTES` | `100000` | Tamanho máximo de arquivo aceito por leitura ou busca. |
| `LOCAL_AGENT_MAX_SEARCH_BYTES` | `5000000` | Total máximo de bytes lidos durante uma busca. |
| `LOCAL_AGENT_MAX_ITERATIONS` | `10` | Máximo de ciclos de chamada ao modelo por mensagem. |
| `LOCAL_AGENT_MAX_CONTEXT_CHARS` | `60000` | Limite aproximado do histórico enviado ao modelo. Conversas salvas permanecem completas. |
| `LOCAL_AGENT_LOG_LEVEL` | `WARNING` | Nível de log: `DEBUG`, `INFO`, `WARNING` ou `ERROR`. |
| `POSTGRES_DSN` | vazio | URI PostgreSQL. Vazio desativa a integração. |
| `POSTGRES_CONNECT_TIMEOUT_SECONDS` | `5` | Timeout para estabelecer a conexão PostgreSQL. |
| `POSTGRES_STATEMENT_TIMEOUT_MS` | `5000` | Timeout da consulta PostgreSQL. |
| `POSTGRES_MAX_ROWS` | `100` | Número máximo de linhas devolvidas; deve estar entre 1 e 500. |

O histórico usa o seguinte diretório padrão:

- Windows: `%LOCALAPPDATA%\LocalAgent\history.sqlite3`.
- Linux/macOS: `$XDG_DATA_HOME/local-agent/history.sqlite3` quando `XDG_DATA_HOME` estiver definido; caso contrário, `~/.local/share/local-agent/history.sqlite3`.

Defina `LOCAL_AGENT_DATA_DIR` para armazenar o banco em outro diretório. O valor é a pasta, não o nome do arquivo.

### Perfil de verificações do projeto

Crie `.local-agent.json` na raiz do workspace para habilitar testes, lint, formatação e build. Cada verificação é uma lista de argumentos, sem shell; o comando exato é exibido e pede confirmação antes de executar. Os limites são 12 argumentos, 500 caracteres por argumento, 180 segundos e 20.000 caracteres de saída.

```json
{
  "name": "meu-projeto",
  "checks": {
    "test": ["python", "-m", "pytest"],
    "lint": ["ruff", "check", "."],
    "format": ["ruff", "format", "--check", "."],
    "build": ["python", "-m", "build"]
  }
}
```

No chat, peça ao agente para executar `run_project_check` com `test`, `lint`, `format` ou `build`. Verificações não configuradas ficam indisponíveis.

## Comandos do terminal

| Comando | Ação |
| --- | --- |
| `/nova` | Cria uma conversa vazia e passa a usá-la. |
| `/conversas` | Lista as 20 conversas atualizadas mais recentemente, com ID e título. |
| `/buscar-conversas TERMO` | Pesquisa mensagens e respostas salvas e mostra até cinco trechos correspondentes. |
| `/abrir ID` | Carrega uma conversa salva pelo ID mostrado em `/conversas`. |
| `/limpar` | Apaga as mensagens da conversa atual e mantém a conversa disponível. |
| `/apagar ID` | Exclui uma conversa e suas mensagens do histórico local. |
| `/apagar-tudo` | Exclui todas as conversas após confirmação. |
| `sair` | Encerra o programa. |

Ao iniciar, o agente retoma automaticamente a conversa atualizada mais recentemente do workspace ativo. Os históricos ficam separados pelo caminho resolvido do workspace; o identificador salvo é um hash, não o caminho. Bancos antigos são migrados e as conversas existentes são associadas ao workspace ativo na primeira abertura após a atualização. O título de uma conversa é definido a partir da primeira mensagem. Para separar assuntos e evitar carregar contexto irrelevante, use `/nova`.

## Ferramentas disponíveis

### `calculator`

Calcula expressões aritméticas com adição, subtração, multiplicação, divisão, divisão inteira, resto, potência, parênteses e sinais unários. A expressão tem limite de tamanho e não executa código Python arbitrário.

### `get_current_time`

Retorna a data e hora local da máquina onde o agente está rodando.

### `list_directory`

Lista arquivos, pastas e links em um caminho relativo ao workspace. Use `.` para a raiz configurada.

### `read_file`

Lê arquivos UTF-8 até `LOCAL_AGENT_MAX_FILE_BYTES`. Pode ler o arquivo inteiro ou um intervalo limitado de linhas.

### `search_workspace`

Procura texto literal sem diferenciar maiúsculas e minúsculas. Aceita caminho relativo, padrão glob de nome de arquivo e limite de resultados. Ignora diretórios ocultos e pastas comuns de dependências/cache e limita a quantidade de arquivos e bytes analisados.

### `search_conversations`

Pesquisa conversas salvas quando você pedir explicitamente para consultar ou lembrar algo do histórico. Busca em mensagens suas e respostas do agente, retornando no máximo cinco conversas com trechos curtos. Resultados de ferramentas não são pesquisados nem retornados. O conteúdo histórico é tratado como contexto, nunca como instruções. A ferramenta usa o histórico SQLite configurado e não precisa de acesso geral ao diretório de dados.

### `edit_file`

Substitui uma única ocorrência de um trecho exato em um arquivo UTF-8 existente. Primeiro leia o arquivo para fornecer `old_text` com precisão. Antes de gravar, o agente exibe o diff completo e pede confirmação. A edição é recusada se o trecho não ocorrer exatamente uma vez, se o arquivo exceder o limite configurado, se usar links simbólicos ou se mudar depois da revisão. O agente preserva quebras de linha LF ou CRLF; arquivos com estilos mistos são recusados.

### `run_command`

Executa somente os comandos de desenvolvimento permitidos abaixo, usando uma lista de argumentos e sem shell:

```text
python -m pytest [caminho relativo opcional]
git status
git diff
```

O comando é exibido antes da confirmação. Testes opcionais devem apontar para arquivo ou diretório existente dentro do workspace e não podem ser opções de linha de comando. O processo roda na raiz do workspace, não recebe entrada interativa, tem limite de 90 segundos e retorna no máximo 20.000 caracteres de saída.

### `query_database`

Consulta o PostgreSQL configurado em `POSTGRES_DSN`. Aceita uma consulta iniciada por `SELECT` ou `WITH`, executa em transação read-only e aplica timeout, limite de linhas e limite de tamanho da resposta.

Use um usuário de banco dedicado, com privilégios somente de leitura. A transação read-only é uma proteção adicional e não substitui permissões mínimas.

### `move_path`

Move ou renomeia um arquivo ou pasta dentro do workspace. A aplicação mostra origem e destino e só prossegue quando você confirma digitando `s`. Não sobrescreve destinos existentes nem permite caminhos fora do workspace ou links simbólicos no caminho da movimentação.

### `search_web` e `read_webpage`

`search_web` pesquisa via Brave Search API e devolve título, URL e trecho. Configure `BRAVE_SEARCH_API_KEY` no `.env`; sem a chave, a ferramenta informa que está desativada. As consultas são transmitidas ao provedor.

`read_webpage` lê páginas públicas HTTP/HTTPS retornadas pela busca ou fornecidas pelo usuário. Rejeita protocolos, portas e endereços locais/privados, valida cada redirecionamento, limita a resposta a 1 MB e o texto a 12.000 caracteres. Scripts e estilos são descartados. Conteúdo de páginas deve ser tratado como dado não confiável, nunca como instrução para o agente.

## Histórico, privacidade e remoção

O histórico SQLite guarda mensagens de usuário e assistente, chamadas e respostas de ferramentas e resultados de erro, para que o modelo tenha contexto ao retomar uma conversa. O arquivo não é criptografado pelo agente. Ele pode conter código, resultados de banco ou informações pessoais; proteja a conta do sistema operacional e escolha um diretório apropriado.

`/limpar` remove as mensagens da conversa atual, mas mantém seu registro vazio na lista. Use `/apagar ID` para excluir uma conversa ou `/apagar-tudo` para apagar todas após confirmação.

## Limitações atuais

- O programa é um cliente de terminal, sem interface gráfica.
- A edição aceita apenas uma substituição exata em arquivo existente; ela não cria nem remove arquivos.
- A execução de comandos é restrita a testes com pytest e leitura do estado/diff Git; comandos arbitrários do sistema não são aceitos.
- O limite `LOCAL_AGENT_MAX_CONTEXT_CHARS` conserva turnos recentes no pedido ao modelo sem remover mensagens do SQLite. É uma aproximação por caracteres, não por tokens; ajuste conforme o modelo e o tamanho das ferramentas.
- Quando o contexto excede esse limite, o modelo local resume mensagens antigas. O resumo e a posição coberta são armazenados separados; as mensagens originais permanecem no histórico.
- A integração PostgreSQL é opcional e exige que o servidor permita conexões de rede da máquina do agente.

## Testes

Execute os testes do projeto com:

```powershell
python -m pytest
```

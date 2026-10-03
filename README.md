# MPS Team Manager

Bot de Discord em Python (`discord.py` 2.x) para gerenciar um time de **MPS** (futebol no Roblox): elenco, partidas, estatísticas, Rank individual, calendário, presença, escalação em imagem e anúncios. Todo o código está em um único arquivo (`main.py`) e os dados ficam em SQLite.

## Recursos

- **Rank individual (D, C, B, A, S)** calculado por gols, assistências, vitórias e MVPs, com pesos e faixas configuráveis. Atualização automática a cada 60 minutos.
- **Perfil do jogador** com botões de Estatísticas, Histórico e Conquistas.
- **Resultados guiados** (`/result`): selecione quem jogou, gols, assistências e MVP por menus, sem digitar nada.
- **Histórico, calendário e painel do time** (`/historico`, `/calendario`, `/time`).
- **Confirmação de presença** (Vou / Não vou / Talvez), persistente após reiniciar o bot.
- **Escalação em imagem** com campo, avatares, nomes, posições e formações 4-3-3, 4-4-2, 3-5-2 e 5-3-2.
- **`/say`**: anúncios com embeds, imagens, banner, botões de link e modelos (aviso, jogo, calendário, convocação, resultado, comunicado).
- **Painel administrativo** (`/admin`) e **configurações por servidor** (`/config`).
- **Logs** de toda alteração, com valores anteriores e novos.
- **Conquistas** (primeiro gol, 10 gols, hat-trick, 5 vitórias seguidas e outras).

## Requisitos

- Python 3.9 ou superior
- Um bot criado no [Discord Developer Portal](https://discord.com/developers/applications)

## Instalação

```bash
git clone https://github.com/SEU_USUARIO/SEU_REPOSITORIO.git
cd SEU_REPOSITORIO
pip install -r requirements.txt
```

## Configurando o token

O token **não fica no código**. Escolha uma das opções:

**Opção 1 — arquivo `.env`** (recomendado):

```bash
cp .env.example .env
# edite o .env e coloque o token em DISCORD_TOKEN=
```

**Opção 2 — variável de ambiente:**

```bash
# Linux / macOS
export DISCORD_TOKEN="seu_token"

# Windows (PowerShell)
$env:DISCORD_TOKEN="seu_token"
```

O `.env` e o banco `*.db` já estão no `.gitignore`. **Nunca** publique seu token. Se ele vazar, gere outro em *Bot → Reset Token*.

Variáveis opcionais:

| Variável | Para que serve |
|---|---|
| `MPS_TEST_GUILD_ID` | ID de um servidor para os comandos aparecerem na hora durante os testes |
| `MPS_DB_PATH` | Caminho do arquivo SQLite (padrão: `mps_team.db`) |

## Executando

```bash
python main.py
```

O banco é criado automaticamente e os comandos slash são registrados na inicialização.

## Adicionando o bot ao servidor

No Developer Portal, em **OAuth2 → URL Generator**:

- Escopos: `bot` e `applications.commands`
- Permissões: Ver canais, Enviar mensagens, Inserir links, Anexar arquivos, Ler histórico de mensagens e Usar comandos de aplicativo (mais *Mencionar @everyone* se for usar essa opção no `/say`)

Não é necessário ativar nenhuma intent privilegiada.

## Comandos

| Área | Comandos |
|---|---|
| Todos | `/perfil`, `/ranking`, `/historico`, `/calendario`, `/time`, `/ajuda`, `/escalação`, `/jogador listar` |
| Administração | `/jogador adicionar\|editar\|remover`, `/gol`, `/assistencia`, `/result`, `/jogo adicionar\|editar\|remover\|listar`, `/escalar`, `/say`, `/admin`, `/config` |

Administradores são quem tem a permissão *Administrador*, o dono do servidor ou quem tem o cargo definido em `/config`. As permissões são verificadas no backend, não apenas nos botões.

## Primeiros passos

1. `/config`: defina canais (logs, resultados, calendário, ranking) e o cargo de jogador.
2. `/jogador adicionar`: cadastre o elenco.
3. `/jogo adicionar`: agende uma partida e publique o aviso com presença.
4. `/escalar` e `/escalação`: monte e gere a imagem da escalação.
5. `/result`: registre o resultado; Rank, conquistas e histórico são atualizados.

## Como o Rank funciona

```
Pontuação = gols × peso_gols + assistências × peso_assist + vitórias × peso_vitórias + MVPs × peso_mvp
```

Padrões: pesos 3 / 2 / 3 / 10. Faixas mínimas: D 0, C 50, B 120, A 250, S 450. Tudo editável em `/config`. As estatísticas são derivadas de um histórico que só cresce (gols, assistências e MVPs), e ajustes manuais ficam registrados nos logs.

## Dados e backup

Tudo fica em `mps_team.db` (SQLite). Faça cópias desse arquivo de vez em quando. Remover um jogador apenas o marca como inativo, então o histórico é preservado.

## Estrutura

```
main.py            # bot completo (banco, comandos, painéis, imagens)
requirements.txt
.env.example
.gitignore
```

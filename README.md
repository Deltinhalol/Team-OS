# TCS/MPS Team Manager

Olá, pessoal! Aqui quem fala é o dev (único) do **Team OS**.

Bom, esse bot foi programado inteiramente por mim, com uma pequena ajuda de IA. Mas calma, eu utilizei IA principalmente para **corrigir falhas, encontrar problemas e melhorar algumas partes do código**.

Então não, você não vai estar usando um bot que simplesmente foi feito por uma IA e jogado aqui KKKKKKKKKKKKKKKK.

Enfim, a partir de agora vou mostrar, passo a passo, tudo o que você precisa saber sobre o **Team OS**, incluindo instalação, configuração, comandos e algumas ajudas para utilizar o bot.

## 1. Instalação

O **Team OS é Open Source**, então você pode acessar e analisar o código do projeto.

Porém, se você puder utilizar o bot normalmente, eu agradeço. Além de facilitar bastante, isso também vai poupar seu tempo.

O bot precisa estar hospedado em algum lugar para funcionar. Então, caso você não tenha conhecimento para instalar e hospedar o projeto no seu próprio PC ou celular, recomendo simplesmente utilizar a versão do bot já disponível.

Mas, caso você saiba como instalar e hospedar o projeto por conta própria, fique à vontade.

> **Resumindo:** você pode instalar por conta própria, mas se puder utilizar o bot normalmente, vai ser muito mais simples.

## 2. Configuração

Depois de adicionar o bot ao servidor, existem alguns passos importantes para deixar tudo funcionando corretamente.

### Primeiros passos

**1. `/config`**

Configure os principais canais e o cargo de jogador:

* Canal de logs
* Canal de resultados
* Canal do calendário
* Canal do ranking
* Cargo de jogador

**2. `/jogador adicionar`**

Cadastre os jogadores que fazem parte do elenco.

**3. `/jogo adicionar`**

Agende uma partida e publique o aviso para os jogadores confirmarem presença.

**4. `/escalar` e `/escalação`**

Monte a escalação da partida e gere a imagem da escalação.

**5. `/result`**

Registre o resultado da partida.

Ao registrar o resultado, informações como **ranking, conquistas e histórico** são atualizadas automaticamente.

## 3. Comandos

### Comandos gerais

| Área          | Comandos                                                                                                                                                                                                                 |
| ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Todos         | `/perfil` · `/ranking` · `/historico` · `/calendario` · `/time` · `/ajuda` · `/escalação` · `/jogador listar`                                                                                                            |
| Administração | `/jogador adicionar` · `/jogador editar` · `/jogador remover` · `/gol` · `/assistencia` · `/result` · `/jogo adicionar` · `/jogo editar` · `/jogo remover` · `/jogo listar` · `/escalar` · `/say` · `/admin` · `/config` |

### Permissões

Os comandos administrativos podem ser utilizados por:

* Usuários com a permissão **Administrador**
* Dono do servidor
* Usuários com o cargo administrativo definido através do `/config`

As permissões são verificadas **diretamente no backend**, e não apenas através dos botões ou da interface do bot.

Isso significa que mesmo que alguém consiga visualizar ou tentar utilizar uma função, o sistema ainda verifica se o usuário realmente possui permissão para executá-la.

## 4. Ajuda

Caso tenha alguma dúvida sobre algum comando ou sistema do Team OS, utilize:

`/ajuda`

O objetivo é deixar o bot o mais simples possível de configurar e utilizar, mesmo para quem nunca mexeu com um sistema desse tipo antes.

## ⚽ Team OS

Um sistema feito para facilitar a organização de times de **TCS/MPS**, centralizando jogadores, partidas, escalações, resultados e estatísticas em um único lugar.

**Organize seu time. Gerencie suas partidas. Jogue.**

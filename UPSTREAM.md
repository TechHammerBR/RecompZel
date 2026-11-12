# O que é do Hookshot e o que é nosso

O RecompZel é um fork de [NotRexed/Hookshot](https://github.com/NotRexed/Hookshot) (GPL-3.0). O remoto `upstream` aponta para ele. Para trazer as novidades: `recompzel\atualizar-fork.ps1` (mostra o que mudou) e `-Aplicar` (junta; se houver conflito, desfaz tudo).

## Arquivos novos (só existem aqui)

| Caminho | Para que serve |
|---|---|
| `INSTALAR-RECOMPZEL.bat` | Entrada simples para o usuário |
| `recompzel/*` | Instalador, build, atalhos pós-instalação, launcher, medição, atualização do fork |
| `gpu/vk/vk_lang.h`, `gpu/vk/vk_lang_pt_br.inc` | Motor de tradução do menu e dicionário embutido |
| `assets/lang/pt-BR.tsv`, `nx2/gen_lang.py` | Dicionário editável e gerador do `.inc` |
| `assets/recompzel.res`, `assets/recompzel_icon.png`, `builder/HookshotBuilder/RecompZel.ico` | Ícone e nome RecompZel |
| `UPSTREAM.md`, `docs/HOOKSHOT-README.md` | Este arquivo e o README original |

## Arquivos do Hookshot que alteramos

| Caminho | O que mudou |
|---|---|
| `readme.md` | Agora é o README do RecompZel (o original está em `docs/HOOKSHOT-README.md`) |
| `gpu/vk/vk_ui.h`, `gpu/vk/vk_menu.cpp`, `gpu/vk/vk_menu.h` | Tradução, linha Idioma, método de geração de quadros no menu |
| `nx2/make_game.py` | Gera `RecompZel.exe` com o nosso ícone |
| `builder/setup/*`, `builder/HookshotBuilder/*`, `builder/py/hookshot_builder/assets/*` | Nome, textos e ícone RecompZel no instalador |

Observação: o diff contra o upstream também mostra arquivos removidos ou diferentes porque o upstream andou depois do nosso último `fetch`. Rode `recompzel\atualizar-fork.ps1 -Aplicar` para ficar em dia.

## Contribuições de fora

| Autor | O que trouxe |
|---|---|
| Jonathan Souza | AMD FSR 4 Frame Generation (Redstone, `gpu/vk/vk_fsr4fg.*`), guarda de HUD contra ghosting (`fg_hudguard.comp` e o anti fantasma do `fg_synth.comp`), profundidade invertida e fallback de modelo no FSR 4, entradas no tamanho de render (resolução dinâmica), eco do jogo (delay) em `host/nn_audio.c`, fullscreen do `options.ini` na abertura (commit 874396cf, de um fork enviado fora do GitHub em 2026-11-12) |

## Fica apontando para o Hookshot de propósito

- `recomplauncher.json` (manifesto de um launcher externo, usa `NotRexed/Hookshot`).
- `builder/setup/setup.c` baixa as partes de `NotRexed/Hookshot` enquanto o nosso repositório não tiver release (`scripts/release_parts.py` já usa as partes do upstream como reserva em forks).

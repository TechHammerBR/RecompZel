# Prompt para o Claude Code (cole tudo abaixo na conversa)

Preciso que você me ajude a achar e corrigir um flicker de cor no RecompZel (port nativo do Zelda: Ocarina of Time do Switch 2 para PC, fork do Hookshot). O repositório é https://github.com/TechHammerBR/RecompZel e o meu jogo está instalado em `C:\Games\RecompZel-TesteLimpo` (ajuste se for outra pasta). Placa: **NVIDIA RTX 4080**. Antes de mudar qualquer código, me explique o que, por que e se vale a pena.

## Contexto: o que está sendo feito

- Eu (TechHammerBR, dono do repositório) e o Jonathan juntamos as nossas versões numa versão "Ultimate". O Jonathan trabalha com o Claude Code numa **AMD RX 9070 XT** (i7-11700F) e eu numa **NVIDIA RTX 4080**.
- O trabalho dele está no **PR #1** (`jonathan/ultimate-fusao`): a fusão (áudio com o Aux da reverberação, guarda de HUD nova, launcher), uma opção no launcher para traduzir os comandos em várias threads (`RX_VK_PARALLEL`, mais FPS em cidades), as correções do CI e um README novo. Se o PR já estiver no `main`, parta do `main`.
- Do lado dele não dá para reproduzir o flicker: só piscou na minha NVIDIA. Por isso a investigação precisa rodar aqui, com você, na minha máquina. Ele já fez os testes da lista abaixo pelo WhatsApp e mandou este pacote com uma ferramenta de busca.

## O problema

- Por **um quadro**, a cena inteira fica **azulada/ciano**: o que está iluminado pelo sol (muros, pedras, chão) fica com o tom das áreas de sombra, como se o sol sumisse naquele quadro, e no seguinte volta ao normal.
- Acontece em **qualquer resolução** e em todo lugar.
- Medido em vídeo (piscadas de um quadro): **101 em 18 s** com DLSS-G 2x + DLAA; **41 em 26 s** e **8 em 21 s** com a geração de quadros e o upscaler desligados. Ou seja: DLSS-G e DLAA **pioram muito**, mas mesmo sem eles ainda pisca um pouco.
- Numa **AMD RX 9070 XT** (máquina do meu amigo, mesmo código) **nunca pisca**.
- **Uma versão antiga não pisca com DLSS** (de antes da fusão "Ultimate" e das correções de FSR). Se você achar essa versão (o `hookshot_log.txt` dela diz o commit na 3ª linha: `hookshot <hash>`), uma **bisseção por git** entre ela e a atual (`cef5e8e` ou o `main` mais novo) acha a mudança culpada em ~7 builds.

## O que já foi descartado (não perca tempo com isso)

- `RX_VK_PROTECT_BARE` (ligado ou desligado): o contador "kept for the GPU" no log fica em 0, a proteção nunca age.
- `RX_VK_PER_QUEUE_FENCES=0`, `RX_VK_WAIT_GPU=1` e os dois juntos (soluções da issue de flicker do Hookshot, NotRexed/Hookshot#1005): ficou igual.
- Nitidez, e o código AMD que veio na fusão (FSR 4, FSR 4 Redstone, guarda de HUD): esse código só roda em AMD (`tests/test_fsr4fg_port.py` confere os gates). O único pedaço da fusão que roda na NVIDIA é o `fg_synth.comp` (geração de quadros do RecompZel), e só com esse método escolhido.
- O cache de shaders do jogo é carimbado com a versão do tradutor (HOOKSHOT_SHADER_STAMP), então um cache velho é improvável. Limpar o cache do driver da NVIDIA (`%LOCALAPPDATA%\NVIDIA\DXCache` e `GLCache`) e renomear `hookshot_pipelines.bin`/`hookshot_programs.*` ainda é um teste barato.

## Suspeitos no caminho do DLSS (mudaram depois da versão antiga boa)

1. `cdf07c9f` **DLSS linear** (11/11): mudou `gpu/vk/shaders/dlss_prep.comp` e `dlss_out.comp` (o shader de saída passou a ler um 3º push constant, `linear_in`). Já achamos um bug real ligado a isso: `gpu/vk/vk_fsr3.cpp` usa o mesmo `DLSS_OUT_COMP_SPV` com push range de **8 bytes** e manda só `pc[2]`, mas o shader lê `pc.linear_in` no offset 8: valor indefinido no caminho do **FSR 3.1**. No caminho do DLSS (`vk_temporal.cpp`) o push está certo (12 bytes, `pc[3]`). Vale conferir se há outro lugar com o mesmo problema.
2. **DLSS Frame Generation** (Streamline: `dd4edbaf`, `717ac813`, `gpu/vk/vk_streamline.cpp`): o DLSS-G recebe só profundidade e movimento.
3. **Merge do Hookshot v2.1.0** (`7e12b32e`).
4. O fork está ~265 commits atrás do Hookshot original (`git remote add upstream https://github.com/NotRexed/Hookshot.git`). Testar a versão mais nova do Hookshot original nesta máquina também diz se já foi corrigido lá.

## Ferramentas que já existem no jogo

- **Busca do shader ao vivo** (nesta pasta): `Abrir com diagnostico.bat` roda o `achar-shader.ps1`. Ele abre o jogo com `RX_VK_DRAW_STATS` (lista os shaders da cena em `diag\draw_stats_*.txt` quando `diag\draw_stats.now` aparece) e `RX_VK_SKIP_FILE` (esconde, ao vivo, os shaders listados; relido a cada 300 ms), e faz a busca por metades perguntando se ainda pisca. O resultado fica em `diag\resultado.txt` e `diag\bissecao.txt`.
  - O `RX_VK_SKIP_FILE` só esconde **desenhos** (draw/mesh). Se o culpado for um **compute** (como a neblina volumétrica, lida um quadro antes na issue NotRexed/Hookshot#570), a busca termina "inconclusiva". Aí use `RX_VK_SKIP_PROG=<prefixos>` (não é ao vivo: vale na abertura e pega computes também) com as chaves `comp` do `draw_stats`.
- `RX_VK_IR=<chave>` + `RX_VK_NO_PROGRAM_CACHE=1`: grava o código traduzido de um shader em `ir_<chave>_*.txt` na pasta do jogo, para analisar o que ele faz.
- Log: `hookshot_log.txt` na pasta do jogo (o jogo gira os logs a cada abertura: a rodada anterior vira `hookshot_log.1.txt`).
- Para olhar quadros: grave em vídeo e extraia os quadros (por exemplo, OpenCV num `pip install --target <pasta temporária> opencv-python-headless`), procurando quadros que diferem dos dois vizinhos enquanto os vizinhos concordam entre si.

## Como compilar

`recompzel\build-game.ps1 -Nup "<arquivo .nup>"` (o launcher também tem **Reconstruir**). Mudar só C++ do `gpu/vk` leva uns minutos; mudar o tradutor de shaders (`vk_shader.cpp` ou o tradutor) refaz os shaders (~1 h).

## O que eu quero no fim

A mudança exata que causa o flicker, a correção mínima (que não mude nada nas placas AMD), um commit numa branch e um pull request no TechHammerBR/RecompZel explicando a causa com os números.

<h1 align="center">RecompZel</h1>

<h4 align="center">The Legend of Zelda: Ocarina of Time (Switch 2) rodando no PC, sem emulador. Vulkan, menu em português do Brasil, NVIDIA DLSS, AMD FSR 4 e geração de quadros para as duas marcas.</h4>

> [!IMPORTANT]
> **Este é o RecompZel, não o Hookshot original.** O RecompZel é um fork do [Hookshot](https://github.com/NotRexed/Hookshot) (GPL-3.0, por NotRexed e colaboradores) com mudanças nossas. Se você abriu o repositório do Hookshot, volte para este: **https://github.com/TechHammerBR/RecompZel**. Use os arquivos **deste** repositório, não os `HookshotBuilder.exe` do projeto original.

> [!NOTE]
> Este repositório **não contém o jogo, chaves nem executável**. Você precisa do seu próprio arquivo do jogo. Tudo que o build gera fica no seu PC e vem do seu jogo. Não compartilhe esses arquivos.

## O que o RecompZel tem de diferente

**Imagem**
- **Upscaler** à escolha no menu do jogo: o do próprio jogo, NVIDIA DLSS, NVIDIA DLAA, AMD FSR 3.1, AMD FSR 4, AMD FSR 4 Nativo (AA) ou Desligado. Só fica disponível o que a sua placa suporta.
- **Geração de quadros** com quatro métodos: o do RecompZel (2x a 8x, qualquer placa), NVIDIA DLSS Frame Generation (RTX 40 e 50), AMD FSR 3.1 (2x) e AMD FSR 4 Frame Generation "Redstone" (2x).
- **Guarda de HUD:** com a geração de quadros, os corações, os botões e o texto não deixam mais "fantasmas", e brilhos sem vetor de movimento (como os olhos do Gohma) não viram manchas pela tela.

**Som**
- A reverberação das salas e o eco das cavernas agora vêm do próprio jogo (efeitos Delay e Aux do áudio do Switch), com uma reserva de 15 ms que tira o chiado e a voz robótica.

**Menu e launcher**
- Menu do jogo (tecla **Insert**) em **português do Brasil**, com linha **Idioma** (Automático segue o idioma do Windows) e cores verde Zelda.
- **RecompZel Launcher:** Jogar, progresso real do build com tempo restante, limite de VRAM, perfis de memória, modo seguro e instalação dos arquivos da NVIDIA e da AMD.
- Ícone e nome **RecompZel** no executável, no instalador e nos atalhos.

O que é do Hookshot e o que é nosso, e quem trouxe cada parte, está em [UPSTREAM.md](UPSTREAM.md). O README original do Hookshot (requisitos, problemas conhecidos, como funciona) está em [docs/HOOKSHOT-README.md](docs/HOOKSHOT-README.md) e continua valendo para tudo que não está dito aqui.

## NVIDIA e AMD

| | NVIDIA | AMD |
|---|---|---|
| Placas | RTX série 20 ou mais nova | Radeon RX série 6000 ou mais nova |
| Upscaler da marca | DLSS e DLAA (RTX) | FSR 4 e FSR 4 Nativo (Radeon RX 9000) |
| Geração de quadros da marca | DLSS Frame Generation (RTX 40: 2x; RTX 50: até 4x) | FSR 4 Redstone (Radeon RX 9000, 2x) |
| Em qualquer placa | Upscaler do jogo, geração de quadros do RecompZel (2x a 8x) e AMD FSR 3.1 onde a placa roda | Igual |

Os arquivos da NVIDIA (DLSS) e da AMD (FSR 4) não vêm no repositório: o launcher instala e confere quando você marca a opção. No menu do jogo, o que a placa não suporta aparece como "(indisponível)". Intel Arc também funciona, com o upscaler do jogo e a geração de quadros do RecompZel.

## Instalar e jogar (Windows)

### O que você precisa

- **O seu arquivo do jogo, na versão certa:** programa `0400486024DEC000`, atualização v131072, build `e0f3ccfa`. Um `.nup` (ou as pastas `romfs` e `exefs`). Outras versões não funcionam.
- Windows 10 ou 11 de 64 bits.
- Placa de vídeo com Vulkan 1.3 e mesh shaders (veja a tabela acima), com o driver atualizado.
- 16 GB de RAM ou mais. Cerca de 60 GB livres durante o build (SSD de preferência).

### Passo a passo

1. Baixe este repositório: botão verde **Code**, depois **Download ZIP**. Extraia o ZIP em uma pasta (por exemplo `C:\RecompZel`).
2. Coloque o seu `.nup` em Downloads, Desktop ou Documentos (o instalador procura lá sozinho).
3. Dê duplo clique em **`INSTALAR-RECOMPZEL.bat`**.
4. Espere o build (de 10 a 45 minutos, ou mais, dependendo do PC). Você pode usar o PC enquanto isso. O launcher mostra a etapa e o tempo restante.
5. Ao terminar, abra o **RecompZel Launcher** e clique em **Jogar**.

Se o instalador não achar o seu `.nup`, informe o caminho:

```
powershell -ExecutionPolicy Bypass -File recompzel\instalar.ps1 -Nup "C:\caminho\arquivo.nup"
```

### Ferramentas de compilação (uma vez)

O build usa um compilador, Python e outras ferramentas (cerca de 400 MB). **Elas são baixadas sozinhas** na primeira vez que você monta o jogo, a partir da release [RecompZel Builder](https://github.com/TechHammerBR/RecompZel/releases/tag/nightly) deste repositório, com o hash de cada parte conferido. Você não precisa baixar nem rodar nada à parte.

### Atualizar

Baixe o ZIP novo (ou `git pull`). Para o jogo já instalado pegar o código novo, use **Reconstruir** no launcher.

## Jogar depois de instalado

Use o **RecompZel Launcher** ou o **Jogar RecompZel.bat** dentro da pasta do jogo (`C:\Games\RecompZel` ou `Games\RecompZel` na sua pasta de usuário). Para criar os atalhos na área de trabalho (ou refazê-los depois de mover a pasta do jogo), rode `recompzel\post-install.ps1`.

Dentro do jogo, **Insert** abre o menu. Na aba **Gráficos** ficam o Upscaler, a Resolução de render, a Nitidez, o Método de geração de quadros e o multiplicador.

### Opções do launcher

| Opção | O que faz |
|---|---|
| Usar AMD FSR 4 | Instala os arquivos do FSR 4 e libera o FSR 4 e o FSR 4 Redstone no menu do jogo (Radeon RX 9000) |
| Usar NVIDIA DLSS | Libera DLSS e DLAA no menu do jogo (RTX). Pede um build com o SDK da NVIDIA (o launcher oferece reconstruir) |
| Usar NVIDIA DLSS Frame Generation | Instala os arquivos da NVIDIA e libera o DLSS-G (RTX 40 e 50) |
| Limite de VRAM | Quanto de memória de vídeo as texturas podem usar (3 GB a 12 GB). 12 GB só em placa de 24 GB |
| Perfil de memória | Padrão, Equilibrado ou Econômico: menos VRAM em troca de recarregar texturas |
| Traduzir os comandos em várias threads | Mais FPS em cidades: no Burgo de Hyrule, de ~39 para ~44 FPS e o pior momento de 14 para 31 (i7-11700F). Desligada por padrão; se aparecer um quadro preto de um instante, desligue |
| Modo seguro | Joga sem FSR 4, DLSS e geração de quadros. Use quando algo der errado |
| Registrar diagnóstico | Deixa o log mais detalhado, para mandar junto de um problema |

## Problemas conhecidos

- **Cor da cena inteira piscando por um quadro (pedras azuladas), visto numa RTX 4080:** em investigação. Se acontecer com você, mande o `hookshot_log.txt` e o `hookshot_options.ini` da pasta do jogo, e diga se para com a Geração de quadros desligada.
- **Linha branca serrilhada contornando barris, caixas e feno, a uma distância fixa do Link (AMD):** vem do shader `23677364611b9855` (o mesmo defeito de NotRexed/Hookshot#2168). Nas placas AMD o launcher já o deixa de fora no `pular-shaders.txt`; escondido, os contornos somem e nada visível falta. Apague a linha do arquivo para vê-lo de novo.
- **Brilho da sala das teias da Árvore Deku (antes do Gohma):** o shader desse brilho saía com um triângulo branco na AMD e hoje fica de fora (arquivo `pular-shaders.txt` na pasta do jogo, criado pelo launcher). Apague a linha do arquivo para vê-lo de novo.
- **DLSS e FSR 4:** coisas que se movem sozinhas (fogo, partículas) podem deixar rastro por enquanto.

## O que tem em cada pasta

| Caminho | O que é |
|---|---|
| `INSTALAR-RECOMPZEL.bat` | Instala o jogo. É o que o usuário final usa |
| `recompzel/` | Nossas ferramentas: `instalar.ps1`, `build-game.ps1`, `post-install.ps1`, `launcher.ps1`, `atualizar-fork.ps1`, `medir-rodada.ps1` |
| `gpu/vk/` | Backend Vulkan: upscalers, geração de quadros (`vk_framegen.cpp`, `vk_fsr4fg.cpp`), menu (`vk_menu.cpp`) e tradução (`vk_lang.h`) |
| `host/nn_audio.c` | O áudio: mixer, reverberação, Delay e Aux |
| `assets/lang/pt-BR.tsv` | Dicionário do menu em português (editável) |
| `nx2/` | Recompilador e gerador do jogo (`make_game.py`, `gen_lang.py`) |
| `builder/` | Fontes do instalador gráfico, já com a marca RecompZel |
| `tests/` | Testes (`python -I -B tests/test_fsr4fg_port.py` confere o port AMD) |
| `docs/development.md` | As variáveis de ambiente para testes (`RX_VK_*`, `HOS_AUDIO_*`) |
| `docs/HOOKSHOT-README.md` | README original do Hookshot |

## Erros comuns

| Mensagem ou sintoma | O que fazer |
|---|---|
| O download das ferramentas falha ou o hash não confere | Verifique a internet e rode de novo; ele continua de onde parou. Se o antivírus apagar arquivos, libere `%LOCALAPPDATA%\RecompZel` |
| "Não achei o arquivo do jogo" | Uma janela pede o arquivo. Ou rode `recompzel\instalar.ps1 -Nup "caminho\arquivo.nup"` |
| "O arquivo é a versão vXXXX" | O RecompZel só aceita a v131072 do jogo (`[v131072]` no nome do `.nup`) |
| Avisos de memória, espaço ou placa no começo | São só avisos. O build pede 16 GB de RAM, cerca de 60 GB livres e uma placa com Vulkan e mesh shaders |
| O build fica minutos sem mexer | Normal. Ele leva de dezenas de minutos a mais de uma hora. O log fica em `%LOCALAPPDATA%\RecompZel\build.log` |
| FSR 4, DLSS ou um método de geração de quadros aparece como "(indisponível)" | A placa não suporta, ou a opção não está marcada no launcher |
| Imagem estranha ou o jogo fecha | Teste com **Modo seguro** no launcher. Se resolver, ligue uma tecnologia por vez para achar a culpada |

O `requirements.txt` da raiz é só para quem desenvolve o código em Linux ou fora do instalador. Quem usa o `INSTALAR-RECOMPZEL.bat` não precisa dele: o build usa o Python que vem nas ferramentas.

## Relatar um problema

O log da última execução é `hookshot_log.txt` na pasta do jogo. As issues deste repositório estão desligadas: mande o log (e o `hookshot_ui_missing.txt`, se existir) para os mantenedores, com a placa de vídeo, o driver e o que estava na tela. Correções são bem-vindas por pull request. Problemas de gráficos gerais (placas AMD/Intel, Linux, etc.) estão descritos em [docs/HOOKSHOT-README.md](docs/HOOKSHOT-README.md#if-something-goes-wrong).

## Créditos e licença

O RecompZel é baseado no [Hookshot](https://github.com/NotRexed/Hookshot) e herda a licença **GPL-3.0** (ver [LICENSE](LICENSE)). As contribuições de cada pessoa estão em [UPSTREAM.md](UPSTREAM.md). Os créditos de todos os componentes de terceiros do projeto original estão em [docs/HOOKSHOT-README.md](docs/HOOKSHOT-README.md#credits). The Legend of Zelda é marca da Nintendo; este projeto não é afiliado a ela.

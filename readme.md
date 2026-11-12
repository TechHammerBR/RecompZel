<h1 align="center">RecompZel</h1>

<h4 align="center">The Legend of Zelda: Ocarina of Time (Switch 2) rodando no PC, sem emulador. Foco em Vulkan, tradução em português do Brasil e geração de quadros própria.</h4>

> [!IMPORTANT]
> **Este é o RecompZel, não o Hookshot original.** O RecompZel é um fork do [Hookshot](https://github.com/NotRexed/Hookshot) (GPL-3.0, por NotRexed e colaboradores) com mudanças nossas. Se você abriu o repositório do Hookshot, volte para este: **https://github.com/TechHammerBR/RecompZel**. Use os arquivos **deste** repositório, não os `HookshotBuilder.exe` do projeto original.

> [!NOTE]
> Este repositório **não contém o jogo, chaves nem executável**. Você precisa do seu próprio arquivo do jogo. Tudo que o build gera fica no seu PC e vem do seu jogo. Não compartilhe esses arquivos.

## O que o RecompZel tem de diferente

- Menu do jogo (tecla **Insert**) em **português do Brasil**, com linha **Idioma** (Automático segue o idioma do Windows).
- O menu informa qual método de geração de quadros está em uso (o nosso, por blocos, ou o AMD FSR 3.1 FG, opcional).
- Ícone e nome **RecompZel** no executável, no instalador e nos atalhos.
- Launcher próprio com progresso do build, medição de rodadas e envio ao GitHub (`recompzel/`).
- Passo pós-instalação: ao terminar o build, cria o atalho **Zelda OoT (RecompZel)** na área de trabalho e um **Jogar RecompZel.bat** na pasta do jogo.

O que é do Hookshot e o que é nosso está listado em [UPSTREAM.md](UPSTREAM.md). O README original do Hookshot (requisitos, problemas conhecidos, como funciona) está em [docs/HOOKSHOT-README.md](docs/HOOKSHOT-README.md) e continua valendo para tudo que não está dito aqui.

## Instalar e jogar (Windows)

### O que você precisa

- **O seu arquivo do jogo, na versão certa:** programa `0400486024DEC000`, atualização v131072, build `e0f3ccfa`. Um `.nup` (ou as pastas `romfs` e `exefs`). Outras versões não funcionam.
- Windows 10 ou 11 de 64 bits.
- Placa de vídeo com Vulkan 1.3 e mesh shaders: NVIDIA RTX série 20 ou mais nova, AMD Radeon RX série 6000 ou mais nova, ou Intel Arc, com o driver atualizado.
- 16 GB de RAM ou mais. Cerca de 60 GB livres durante o build (SSD de preferência).

### Passo a passo

1. Baixe este repositório: botão verde **Code**, depois **Download ZIP**. Extraia o ZIP em uma pasta (por exemplo `C:\RecompZel`).
2. Coloque o seu `.nup` em Downloads, Desktop ou Documentos (o instalador procura lá sozinho).
3. Dê duplo clique em **`INSTALAR-RECOMPZEL.bat`**.
4. Espere o build (de 10 a 45 minutos, ou mais, dependendo do PC). Você pode usar o PC enquanto isso.
5. Ao terminar, use o atalho **Zelda OoT (RecompZel)** na área de trabalho.

Se o instalador não achar o seu `.nup`, informe o caminho:

```
powershell -ExecutionPolicy Bypass -File recompzel\instalar.ps1 -Nup "C:\caminho\arquivo.nup"
```

### Ferramentas de compilação (uma vez)

O build usa um compilador, Python e outras ferramentas (cerca de 400 MB). **Elas são baixadas sozinhas** na primeira vez que você monta o jogo, a partir da release [RecompZel Builder](https://github.com/TechHammerBR/RecompZel/releases/tag/nightly) deste repositório, com o hash de cada parte conferido. Você não precisa baixar nem rodar nada à parte.

## Jogar depois de instalado

Use **Zelda OoT (RecompZel)** na área de trabalho, ou **Jogar RecompZel.bat** dentro da pasta do jogo (`C:\Games\RecompZel` ou `Games\RecompZel` na sua pasta de usuário). Se mover a pasta do jogo, rode `recompzel\post-install.ps1` para refazer os atalhos.

Se preferir o launcher (menu com Jogar, progresso do build e opções), use **RecompZel Launcher** na área de trabalho.

Dentro do jogo, **Insert** abre o menu (idioma, qualidade, geração de quadros, upscaling).

## Atualizar para a versão mais nova

O jogo já instalado **não** atualiza sozinho. Para pegar correções e melhorias novas:

1. Abra o **RecompZel Launcher**.
2. Clique em **Reconstruir o jogo**. Ele busca a versão mais nova sozinho e recompila (leva uns 5 minutos; o que já foi compilado antes é reaproveitado).
3. Quando terminar, clique em **Jogar**.

O botão **Atualizar o RecompZel** é outra coisa, separada: ele só atualiza o launcher (o painel com os botões), não o jogo. Quem busca a versão nova do jogo e recompila é o **Reconstruir o jogo**.

## O que tem em cada pasta

| Caminho | O que é |
|---|---|
| `INSTALAR-RECOMPZEL.bat` | Instala e cria o atalho. É o que o usuário final usa |
| `recompzel/` | Nossas ferramentas: `instalar.ps1`, `build-game.ps1`, `post-install.ps1`, `launcher.ps1`, `atualizar-fork.ps1` |
| `gpu/vk/` | Backend Vulkan. `vk_lang.h` é o motor de tradução do menu |
| `assets/lang/pt-BR.tsv` | Dicionário do menu em português (editável) |
| `nx2/` | Recompilador e gerador do jogo (`make_game.py`, `gen_lang.py`) |
| `builder/` | Fontes do instalador gráfico, já com a marca RecompZel |
| `docs/HOOKSHOT-README.md` | README original do Hookshot |

## Erros comuns

| Mensagem ou sintoma | O que fazer |
|---|---|
| O download das ferramentas falha ou o hash não confere | Verifique a internet e rode de novo; ele continua de onde parou. Se o antivírus apagar arquivos, libere `%LOCALAPPDATA%\RecompZel` |
| "Não achei o arquivo do jogo" | Uma janela pede o arquivo. Ou rode `recompzel\instalar.ps1 -Nup "caminho\arquivo.nup"` |
| "O arquivo é a versão vXXXX" | O RecompZel só aceita a v131072 do jogo (`[v131072]` no nome do `.nup`) |
| Avisos de memória, espaço ou placa no começo | São só avisos. O build pede 16 GB de RAM, cerca de 60 GB livres e uma placa com Vulkan e mesh shaders |
| O build fica minutos sem mexer | Normal. Ele leva de dezenas de minutos a mais de uma hora. O log fica em `%LOCALAPPDATA%\RecompZel\build.log` |

O `requirements.txt` da raiz é só para quem desenvolve o código em Linux ou fora do instalador. Quem usa o `INSTALAR-RECOMPZEL.bat` não precisa dele: o build usa o Python que vem nas ferramentas.

## Problemas

O log da última execução é `hookshot_log.txt` na pasta do jogo. Em caso de travamento, abra uma [issue](https://github.com/TechHammerBR/RecompZel/issues) deste repositório e anexe o log e o `hookshot_ui_missing.txt` (se existir). Problemas de gráficos gerais (placas AMD/Intel, Linux, etc.) estão descritos em [docs/HOOKSHOT-README.md](docs/HOOKSHOT-README.md#if-something-goes-wrong).

## Créditos e licença

O RecompZel é baseado no [Hookshot](https://github.com/NotRexed/Hookshot) e herda a licença **GPL-3.0** (ver [LICENSE](LICENSE)). Os créditos de todos os componentes de terceiros do projeto original estão em [docs/HOOKSHOT-README.md](docs/HOOKSHOT-README.md#credits). The Legend of Zelda é marca da Nintendo; este projeto não é afiliado a ela.

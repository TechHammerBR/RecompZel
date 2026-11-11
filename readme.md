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

O build usa um compilador e ferramentas que são baixados por um instalador. Se o `INSTALAR-RECOMPZEL.bat` disser que as ferramentas não estão instaladas:

- Baixe **`RecompZelBuilder.exe`** na aba [Releases](https://github.com/TechHammerBR/RecompZel/releases) deste repositório, rode uma vez e feche.
- Enquanto este repositório não tiver uma release, o único jeito é rodar o `HookshotBuilder.exe` do projeto original **somente para baixar as ferramentas** (não use o jogo que ele gera). Esta observação sai daqui quando a release do RecompZel existir.

Depois, abra o `INSTALAR-RECOMPZEL.bat` de novo.

## Jogar depois de instalado

Use **Zelda OoT (RecompZel)** na área de trabalho, ou **Jogar RecompZel.bat** dentro da pasta do jogo (`C:\Games\RecompZel` ou `Games\RecompZel` na sua pasta de usuário). Se mover a pasta do jogo, rode `recompzel\post-install.ps1` para refazer os atalhos.

Se preferir o launcher (menu com Jogar, progresso do build e opções), use **RecompZel Launcher** na área de trabalho.

Dentro do jogo, **Insert** abre o menu (idioma, qualidade, geração de quadros, upscaling).

## O que tem em cada pasta

| Caminho | O que é |
|---|---|
| `INSTALAR-RECOMPZEL.bat` | Instala e cria o atalho. É o que o usuário final usa |
| `recompzel/` | Nossas ferramentas: `instalar.ps1`, `build-game.ps1`, `post-install.ps1`, `launcher.ps1`, `atualizar-fork.ps1`, `enviar-github.ps1` |
| `gpu/vk/` | Backend Vulkan. `vk_lang.h` é o motor de tradução do menu |
| `assets/lang/pt-BR.tsv` | Dicionário do menu em português (editável) |
| `nx2/` | Recompilador e gerador do jogo (`make_game.py`, `gen_lang.py`) |
| `builder/` | Fontes do instalador gráfico, já com a marca RecompZel |
| `docs/HOOKSHOT-README.md` | README original do Hookshot |

## Problemas

O log da última execução é `hookshot_log.txt` na pasta do jogo. Em caso de travamento, abra uma [issue](https://github.com/TechHammerBR/RecompZel/issues) deste repositório e anexe o log e o `hookshot_ui_missing.txt` (se existir). Problemas de gráficos gerais (placas AMD/Intel, Linux, etc.) estão descritos em [docs/HOOKSHOT-README.md](docs/HOOKSHOT-README.md#if-something-goes-wrong).

## Créditos e licença

O RecompZel é baseado no [Hookshot](https://github.com/NotRexed/Hookshot) e herda a licença **GPL-3.0** (ver [LICENSE](LICENSE)). Os créditos de todos os componentes de terceiros do projeto original estão em [docs/HOOKSHOT-README.md](docs/HOOKSHOT-README.md#credits). The Legend of Zelda é marca da Nintendo; este projeto não é afiliado a ela.

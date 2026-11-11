# launcher.ps1  -  RecompZel Launcher v3 (original, feito para o nosso projeto)
# Uso: powershell -ExecutionPolicy Bypass -File launcher.ps1   (ou o RecompZel-Launcher.exe)
# Le o build.log e a pasta de trabalho. Nao apaga nada. Reconstruir pede confirmacao.
# Idioma: Portugues (Brasil) ou English, no canto superior esquerdo. Perfis de jogos: games.json, na pasta do launcher.
# A pasta do jogo e C:\Games\RecompZel. Se ainda existir so a antiga (C:\Games\HookshotDev), ela continua sendo usada.

Add-Type -AssemblyName PresentationFramework, PresentationCore, WindowsBase

# Os scripts ficam onde este esta (C:\DEV no PC do desenvolvedor, %LOCALAPPDATA%\RecompZel para quem usa o .exe); os dados (perfil, logs, rodadas)
# ficam na mesma pasta, exceto quando o launcher roda de dentro do repositorio (pasta recompzel): ai vao para %LOCALAPPDATA%\RecompZel.
$AppDir       = if ((Split-Path $PSScriptRoot -Leaf) -eq 'recompzel' -and (Test-Path (Join-Path (Split-Path $PSScriptRoot -Parent) 'nx2\make_game.py'))) { Join-Path $env:LOCALAPPDATA 'RecompZel' } else { $PSScriptRoot }
New-Item -ItemType Directory -Force -Path $AppDir | Out-Null
$ProfilesPath = Join-Path $AppDir 'games.json'
$Cfg          = Join-Path $AppDir 'launcher-settings.json'
$W = @{ read = 15; lift = 10; compile = 60; finish = 15 }   # pesos do percentual total
$script:lang = 'pt'

# ---------- Textos (pt = Portugues do Brasil, en = English) ----------
$STR = @{}
$STR['pt'] = @{
    subtitle = 'Switch 2, recompilado para PC'
    needs = 'Voce precisa do seu proprio arquivo do jogo (.nup). Nada e baixado da internet.'
    play = 'Jogar'
    play_tip = 'Inicia o jogo. Fica desativado ate o jogo estar pronto.'
    build = 'Construir o jogo'
    rebuild = 'Reconstruir o jogo'
    build_tip = 'Cria o jogo no seu PC a partir do seu arquivo. Demora de dezenas de minutos a mais de uma hora. Voce pode usar o PC normalmente.'
    folder = 'Abrir a pasta do jogo'
    folder_tip = 'Abre a pasta onde o jogo foi montado.'
    report = 'Copiar relatorio para suporte'
    report_tip = 'Copia o final do registro do build. Cole numa conversa para pedir ajuda.'
    upd = 'Atualizar o RecompZel'
    upd_avail = 'Atualizar o RecompZel (ha novidade!)'
    upd_tip = 'Baixa a versao mais nova do launcher e do codigo do jogo direto do GitHub. Depois, Reconstruir aplica as mudancas do jogo.'
    upd_ask = 'Baixar e instalar a atualizacao do RecompZel agora? O launcher fecha e abre de novo sozinho.'
    upd_none = 'Voce ja esta com a versao mais nova.'
    upd_fail = 'Nao consegui atualizar agora: {0}'
    upd_src_ok = 'Codigo do jogo atualizado. Clique em Reconstruir para aplicar (so recompila o que mudou).'
    vram_t = 'Memoria de video para texturas'
    vram_d = 'Padrao do jogo (70% da VRAM, ate 6 GB)'
    vram_tip = 'Quanta memoria da placa de video o jogo pode usar para texturas. Valores maiores ajudam nas texturas embaralhadas, se a placa tiver folga. Padrao: o jogo decide.'
    mesh_t = 'Modo dos mesh shaders (desenho 3D)'
    mesh_0 = 'Automatico (recomendado)'
    mesh_1 = 'Nativo (usa o recurso da placa)'
    mesh_2 = 'Compute (compativel, mais lento ao preparar)'
    mesh_tip = 'Escolhe como o jogo desenha a geometria 3D. Trocar isso faz o jogo refazer o cache de shaders na proxima vez que abrir, e isso demora. Automatico e o mais seguro. So muda com o jogo fechado, e o launcher guarda uma copia da configuracao antiga (hookshot_options.ini.bak).'
    mesh_noini = 'Abra o jogo uma vez para criar as opcoes.'
    mesh_close = 'Feche o jogo antes de trocar.'
    mesh_saved = 'Salvo. Na proxima vez que abrir, o jogo refaz o cache de shaders.'
    mesh_fail = 'Nao consegui salvar: {0}'
    mesh_ok = 'Valor atual lido das opcoes do jogo.'
    up_t = 'Upload de texturas por quadro'
    mem_t = 'Perfil de memoria (RAM e VRAM)'
    up_0 = 'Padrao do jogo (40 ms)'
    up_1 = '120 ms'
    up_2 = 'Sem adiamento (0 ms)'
    fg_t = 'Metodo de geracao de quadros'
    fg_0 = 'RecompZel (padrao, 2x a 8x)'
    fg_1 = 'AMD FSR 3.1 (so 2x)'
    fg_2 = 'Desligado (sem geracao de quadros)'
    diag = 'Registrar diagnostico (buffer sem conexao)'
    ram_save = 'Economizar RAM (nao carrega o cache de shaders: 1 a 3 GB a menos; a abertura demora uns segundos a mais)'
    ram_tip = 'RX_VK_PCACHE_LOAD=0'
    mem_now = 'Jogo agora: RAM {0}, VRAM {1}'
    fsr = 'Usar AMD FSR 4 (mais quadros por segundo)'
    fsr_off = 'Desligado. Se ligar, o launcher cuida do resto.'
    fsr_rebuild = 'O jogo sera reconstruido uma vez, com FSR 4, ao clicar em Jogar.'
    fsr_dl = 'Ao clicar em Jogar, baixa um componente de 14 MB (so na primeira vez).'
    fsr_ready = 'Pronto. O FSR 4 sera usado ao clicar em Jogar.'
    fsr_q = 'O FSR 4 precisa de um componente de terceiros (fsr4vk, licenca GPLv3, cerca de 14 MB).{n}{n}Ele nao e da AMD nem nosso: vem do GitHub (0xCydral/bloodborne_pc) e o launcher confere o arquivo antes de usar.{n}{n}Baixar agora? Se escolher Nao, o jogo abre sem FSR 4.'
    fsr_dling = 'Baixando o componente do FSR 4...'
    dsr = 'Usar NVIDIA DLSS (reescalonamento, RTX)'
    dsr_off = 'Desligado. Se ligar, o launcher reconstroi o jogo uma vez com o SDK da NVIDIA e cuida do resto.'
    dsr_rebuild = 'O jogo sera reconstruido uma vez, com o DLSS da NVIDIA, ao clicar em Jogar (baixa o SDK da NVIDIA no build).'
    dsr_ready = 'Pronto. O DLSS sera usado ao clicar em Jogar (o menu Insert, linha Upscaler, tambem mostra DLSS e DLAA).'
    dsr_nogpu = 'Nao encontrei uma NVIDIA RTX neste PC. O DLSS nao funciona nesta placa.'
    dsr_q = 'O DLSS (reescalonamento) usa o SDK e o componente da NVIDIA (licenca NVIDIA RTX SDKs, so para placas NVIDIA). Eles nao sao nossos: o build baixa os arquivos oficiais do GitHub da NVIDIA e confere cada um.{n}{n}O jogo precisa ser reconstruido uma vez com o SDK (o que ja esta pronto e reaproveitado, entao demora bem menos que a primeira vez).{n}{n}Aceita a licenca da NVIDIA e reconstruir agora? Se escolher Nao, o jogo abre sem o DLSS.'
    dlss = 'Usar NVIDIA DLSS Frame Generation (RTX 40/50)'
    dlss_off = 'Desligado. Se ligar, o launcher baixa os componentes da NVIDIA e cuida do resto.'
    dlss_dl = 'Ao clicar em Jogar, baixa os componentes da NVIDIA (cerca de 276 MB, so na primeira vez).'
    dlss_ready = 'Pronto. No jogo (menu Insert, aba Graficos), a linha Metodo de geracao de quadros escolhe o DLSS e a linha Geracao de quadros, o multiplicador (2x). Precisa do DLSS (reescalonamento) ligado.'
    dlss_nogpu = 'Nao encontrei uma NVIDIA RTX serie 40 ou 50 neste PC. O DLSS Frame Generation nao funciona nesta placa.'
    dlss_q = 'O DLSS Frame Generation precisa de componentes da NVIDIA (Streamline 2.14.16: 6 arquivos, uso so em placas NVIDIA, licenca NVIDIA RTX SDKs).{n}{n}Eles nao sao nossos: o launcher baixa o pacote oficial do GitHub da NVIDIA (cerca de 276 MB), extrai so esses 6 arquivos e confere cada um antes de usar.{n}{n}Baixar agora? Se escolher Nao, o jogo abre sem DLSS Frame Generation.'
    dlss_dling = 'Baixando o pacote da NVIDIA (276 MB), aguarde...'
    dlss_done = 'Componentes do DLSS Frame Generation instalados.'
    dlss_fail = 'Nao consegui instalar o DLSS Frame Generation: {0}{n}{n}O jogo abre sem ele.'
    dlss_e_pkg = 'o pacote nao tem o arquivo esperado: {0}'
    dlss_e_hash = 'o arquivo {0} nao confere com o esperado (hash diferente)'
    fsr_done = 'Componente do FSR 4 instalado.'
    fsr_fail = 'Nao consegui instalar o FSR 4: {0}{n}{n}O jogo abre sem FSR 4.'
    fsr_e_pkg = 'o pacote nao tem o componente esperado'
    fsr_e_hash = 'o arquivo baixado nao confere com o esperado (hash diferente)'
    fsr_q_rebuild = 'Este jogo foi construido sem suporte ao FSR 4. Para usar, ele precisa ser reconstruido uma vez (o que ja esta pronto e reaproveitado, entao demora bem menos que a primeira vez).{n}{n}Reconstruir agora? Se escolher Nao, o jogo abre sem FSR 4.'
    help = 'Passe o mouse sobre um botao para ver o que ele faz.'
    tech_t = 'Tecnologias de imagem'
    tech_gpu = 'Sua placa: {0}'
    tech_gpu_none = 'nao consegui ler a placa de video'
    tech_all = 'Instalar tudo para a minha placa'
    tech_all_q = 'Vou preparar para a sua placa: {0}.{n}{n}Isso baixa componentes de terceiros conforme a placa (NVIDIA: Streamline, cerca de 276 MB; AMD: componente do FSR 4, cerca de 14 MB), confere o hash de cada arquivo e liga as opcoes certas. O DLSS (reescalonamento) pede reconstruir o jogo uma vez.{n}{n}Aceita as licencas da NVIDIA (NVIDIA RTX SDKs) e do componente do FSR 4 (GPLv3) e quer continuar? Se escolher Nao, nada e baixado.'
    tech_none = 'Nao encontrei uma placa compativel com DLSS (NVIDIA RTX) ou FSR 4 (AMD) neste PC. O jogo usa o upscaler e a geracao de quadros dele.'
    tech_done = 'Tudo pronto para a sua placa. Escolha o upscaler e o metodo de geracao de quadros dentro do jogo (menu Insert, aba Graficos).'
    tech_done_rebuild = 'Componentes instalados. Falta so reconstruir o jogo uma vez (botao Reconstruir o jogo) para ligar o DLSS.'
    tech_fail = 'Algumas opcoes nao foram instaladas. O jogo abre sem elas.'
    safe = 'Modo seguro (jogar sem tecnologias extras)'
    safe_on = 'Ligado: o jogo abre sem DLSS, FSR 4 e Streamline, so com o upscaler e a geracao de quadros dele.'
    safe_off = 'Desligado. Ligue se o jogo travar, para testar sem as tecnologias acima.'
    help_tech = 'O launcher detecta a sua placa e so oferece o que ela suporta. Dentro do jogo (menu Insert, aba Graficos) voce escolhe o upscaler e o metodo de geracao de quadros.'
    badge_ok = 'Ativo'
    badge_off = 'Nao incluido'
    badge_todo = 'Falta instalar'
    badge_no = 'Sem suporte'
    badge_exp = 'Experimental'
    badge_safe = 'Modo seguro'
    tn_dsr = 'NVIDIA DLSS (reescalonamento e DLAA)'
    tn_dlss = 'NVIDIA DLSS Frame Generation'
    tn_fsr = 'AMD FSR 4'
    tech_intro = 'Tudo que a sua placa suporta fica ativo. Depois e so escolher no jogo (menu Insert, aba Graficos): o Upscaler e o metodo de geracao de quadros.'
    st_dsr_on = 'Ativo. No jogo, a linha Upscaler escolhe DLSS ou DLAA.'
    st_dsr_todo = 'Ativado na proxima reconstrucao do jogo (uma vez; o launcher cuida disso).'
    st_dlss_on = 'Ativo. No jogo, a linha Metodo de geracao de quadros escolhe o DLSS e a linha Geracao de quadros, o multiplicador.'
    st_dlss_todo = 'Os componentes da NVIDIA (cerca de 276 MB) sao baixados uma vez, ao clicar em Jogar ou em Instalar tudo.'
    st_fsr_on = 'Ativo. No jogo, a linha Upscaler escolhe o FSR 4.'
    st_fsr_rebuild = 'Ativado na proxima reconstrucao do jogo (uma vez).'
    st_fsr_todo = 'O componente do FSR 4 (cerca de 14 MB) e baixado uma vez, ao clicar em Jogar ou em Instalar tudo.'
    st_fsr_other = 'Pensado para placas AMD e nao incluido nesta placa. O FSR 3.1 do proprio jogo continua no menu.'
    st_safe = 'Modo seguro ligado: nao usado.'
    help_tune = 'Rodada 2: texturas ASTC novas ficam provisorias quando o carregamento passa do limite por quadro. Teste 120 ms ou Sem adiamento. O diagnostico registra o buffer sem conexao no log.'
    lbl_now = 'O que esta acontecendo agora'
    lbl_steps = 'Etapas'
    lbl_next = 'Proximo passo'
    lbl_notes = 'O que voce viu na ultima partida (salvo junto com o log)'
    lbl_summary = 'Resumo da ultima rodada'
    summary_ph = 'Aparece aqui quando voce fechar o jogo.'
    st_err = 'Algo deu errado'
    now_err = 'O build encontrou um erro e pode ter parado.'
    next_err = 'Clique em "Copiar relatorio para suporte" e cole na conversa para receber ajuda.'
    st_ready = 'Pronto para jogar'
    now_ready = 'O jogo foi construido e esta instalado no seu PC.'
    next_ready = 'Clique em Jogar.'
    st_none = 'Ainda nao comecou'
    next_none = 'Clique em "Construir o jogo".'
    st_build = 'Construindo o jogo'
    now_read = 'Copiando os arquivos do seu jogo para o PC. Isso so usa o disco.'
    now_lift = 'Convertendo o codigo do Switch 2 para codigo de PC. E uma etapa rapida.'
    now_compile = 'Transformando esse codigo em programa. E a etapa mais longa e deixa o processador bem ocupado.'
    now_finish = 'Finalizando: juntando as pecas e preparando os efeitos graficos.'
    now_shaders = 'Preparando os efeitos graficos (shaders) da sua placa de video. Leva alguns minutos, so desta vez.'
    st_shaders = 'Preparando os shaders'
    next_shaders = 'Quando terminar, o botao Jogar liga sozinho. A janela do build fecha sozinha.'
    next_build = 'Nao precisa fazer nada. Pode deixar esta janela aberta e usar o PC normalmente.'
    act_pre = 'Ultima atividade ha '
    act_post = ''
    eta_pre = 'Faltam cerca de '
    eta_post = ''
    lt1 = 'menos de 1 minuto'
    s1 = '{0} 1. Ler o jogo ({1:N0}%)'
    s2 = '{0} 2. Traduzir para PC ({1:N0}%)'
    s3 = '{0} 3. Montar o programa ({1:N0}%, {2} de {3} pecas)'
    s4 = '{0} 4. Finalizar e empacotar ({1:N0}%)'
    q_build = 'Iniciar o build do jogo? Pode levar mais de uma hora e usa bastante o processador.'
    e_script = 'Nao achei o script de build: {0}'
    e_script2 = 'Nao achei o script: {0}'
    nup_use = 'Usar este arquivo do jogo?{n}{n}{0}{n}{n}Sim = usar este.   Nao = escolher outro arquivo.'
    nup_title = 'Escolha o arquivo do jogo (.nup) do Zelda Ocarina of Time'
    nup_filter = 'Arquivo do jogo (*.nup)|*.nup|Todos os arquivos|*.*'
    nup_none = 'Sem o arquivo do jogo (.nup) o build nao comeca.'
    rep_copied = 'Relatorio copiado. Cole na conversa com Ctrl+V.'
    started = 'Jogo iniciado. Ao fechar o jogo, o log desta rodada e salvo na pasta rodadas do launcher.'
    saved = 'Rodada salva: {0}'
}
$STR['en'] = @{
    subtitle = 'Switch 2, recompiled for PC'
    needs = 'You need your own copy of the game (.nup). Nothing is downloaded from the internet.'
    play = 'Play'
    play_tip = 'Starts the game. Disabled until the game is ready.'
    build = 'Build the game'
    rebuild = 'Rebuild the game'
    build_tip = 'Builds the game on your PC from your own file. Takes from tens of minutes to over an hour. You can keep using the PC.'
    folder = 'Open the game folder'
    folder_tip = 'Opens the folder where the game was built.'
    report = 'Copy report for support'
    report_tip = 'Copies the end of the build log. Paste it into a chat to ask for help.'
    upd = 'Update RecompZel'
    upd_avail = 'Update RecompZel (news!)'
    upd_tip = 'Downloads the newest launcher and game code straight from GitHub. Then Rebuild applies the game changes.'
    upd_ask = 'Download and install the RecompZel update now? The launcher closes and opens again by itself.'
    upd_none = 'You already have the newest version.'
    upd_fail = 'Could not update now: {0}'
    upd_src_ok = 'Game code updated. Click Rebuild to apply it (only what changed is recompiled).'
    vram_t = 'Video memory for textures'
    vram_d = 'Game default (70% of VRAM, up to 6 GB)'
    vram_tip = 'How much graphics card memory the game may use for textures. Larger values help with scrambled textures, if the card has room. Default: the game decides.'
    mesh_t = 'Mesh shader mode (3D drawing)'
    mesh_0 = 'Automatic (recommended)'
    mesh_1 = 'Native (uses the GPU feature)'
    mesh_2 = 'Compute (compatible, slower to prepare)'
    mesh_tip = 'Chooses how the game draws 3D geometry. Changing it makes the game rebuild its shader cache the next time it opens, which takes a while. Automatic is the safest. It only changes with the game closed, and the launcher keeps a copy of the old settings (hookshot_options.ini.bak).'
    mesh_noini = 'Open the game once to create its options.'
    mesh_close = 'Close the game before changing this.'
    mesh_saved = 'Saved. The next time it opens, the game rebuilds its shader cache.'
    mesh_fail = 'Could not save: {0}'
    mesh_ok = 'Current value read from the game options.'
    up_t = 'Texture upload per frame'
    mem_t = 'Memory profile (RAM and VRAM)'
    up_0 = 'Game default (40 ms)'
    up_1 = '120 ms'
    up_2 = 'No deferral (0 ms)'
    fg_t = 'Frame generation method'
    fg_0 = 'RecompZel (default, 2x to 8x)'
    fg_1 = 'AMD FSR 3.1 (2x only)'
    fg_2 = 'Off (no frame generation)'
    diag = 'Log diagnostics (unbound buffer)'
    ram_save = 'Save RAM (does not load the shader cache: 1 to 3 GB less; the start takes a few seconds longer)'
    ram_tip = 'RX_VK_PCACHE_LOAD=0'
    mem_now = 'Game now: RAM {0}, VRAM {1}'
    fsr = 'Use AMD FSR 4 (higher frame rate)'
    fsr_off = 'Off. If you turn it on, the launcher handles the rest.'
    fsr_rebuild = 'The game will be rebuilt once, with FSR 4, when you click Play.'
    fsr_dl = 'When you click Play, it downloads a 14 MB component (first time only).'
    fsr_ready = 'Ready. FSR 4 will be used when you click Play.'
    fsr_q = 'FSR 4 needs a third-party component (fsr4vk, GPLv3 license, about 14 MB).{n}{n}It is neither AMD''s nor ours: it comes from GitHub (0xCydral/bloodborne_pc) and the launcher checks the file before using it.{n}{n}Download now? If you choose No, the game opens without FSR 4.'
    fsr_dling = 'Downloading the FSR 4 component...'
    dsr = 'Use NVIDIA DLSS (upscaling, RTX)'
    dsr_off = 'Off. If you turn it on, the launcher rebuilds the game once with NVIDIA''s SDK and handles the rest.'
    dsr_rebuild = 'The game will be rebuilt once, with NVIDIA DLSS, when you click Play (the build downloads NVIDIA''s SDK).'
    dsr_ready = 'Ready. DLSS will be used when you click Play (the Insert menu''s Upscaler row also shows DLSS and DLAA).'
    dsr_nogpu = 'No NVIDIA RTX card found in this PC. DLSS does not work on this card.'
    dsr_q = 'DLSS (upscaling) uses NVIDIA''s SDK and component (NVIDIA RTX SDKs license, NVIDIA GPUs only). They are not ours: the build downloads NVIDIA''s official files from GitHub and checks each one.{n}{n}The game must be rebuilt once with the SDK (what is already done is reused, so it takes much less than the first time).{n}{n}Accept NVIDIA''s license and rebuild now? If you choose No, the game opens without DLSS.'
    dlss = 'Use NVIDIA DLSS Frame Generation (RTX 40/50)'
    dlss_off = 'Off. If you turn it on, the launcher downloads the NVIDIA components and handles the rest.'
    dlss_dl = 'When you click Play, it downloads the NVIDIA components (about 276 MB, first time only).'
    dlss_ready = 'Ready. In the game (Insert menu, Graphics tab), the Frame generation method row picks DLSS and the Frame generation row the multiplier (2x). It needs DLSS upscaling on.'
    dlss_nogpu = 'No NVIDIA RTX 40 or 50 series card found in this PC. DLSS Frame Generation does not work on this card.'
    dlss_q = 'DLSS Frame Generation needs NVIDIA components (Streamline 2.14.16: 6 files, NVIDIA GPUs only, NVIDIA RTX SDKs license).{n}{n}They are not ours: the launcher downloads the official package from NVIDIA''s GitHub (about 276 MB), extracts only those 6 files and checks each one before using it.{n}{n}Download now? If you choose No, the game opens without DLSS Frame Generation.'
    dlss_dling = 'Downloading the NVIDIA package (276 MB), please wait...'
    dlss_done = 'DLSS Frame Generation components installed.'
    dlss_fail = 'Could not install DLSS Frame Generation: {0}{n}{n}The game opens without it.'
    dlss_e_pkg = 'the package does not contain the expected file: {0}'
    dlss_e_hash = 'the file {0} does not match the expected one (different hash)'
    fsr_done = 'FSR 4 component installed.'
    fsr_fail = 'Could not install FSR 4: {0}{n}{n}The game opens without FSR 4.'
    fsr_e_pkg = 'the package does not contain the expected component'
    fsr_e_hash = 'the downloaded file does not match the expected one (different hash)'
    fsr_q_rebuild = 'This game was built without FSR 4 support. To use it, it must be rebuilt once (what is already done is reused, so it takes much less than the first time).{n}{n}Rebuild now? If you choose No, the game opens without FSR 4.'
    help = 'Hover over a button to see what it does.'
    tech_t = 'Image technologies'
    tech_gpu = 'Your GPU: {0}'
    tech_gpu_none = 'could not read the graphics card'
    tech_all = 'Install everything for my GPU'
    tech_all_q = 'I will set up for your GPU: {0}.{n}{n}This downloads third-party components depending on the card (NVIDIA: Streamline, about 276 MB; AMD: the FSR 4 component, about 14 MB), checks each file''s hash and turns the right options on. DLSS (upscaling) needs the game rebuilt once.{n}{n}Do you accept NVIDIA''s license (NVIDIA RTX SDKs) and the FSR 4 component''s (GPLv3) and want to continue? If you choose No, nothing is downloaded.'
    tech_none = 'No DLSS-capable (NVIDIA RTX) or FSR 4-capable (AMD) card found in this PC. The game uses its own upscaler and frame generation.'
    tech_done = 'All set for your GPU. Pick the upscaler and the frame generation method inside the game (Insert menu, Graphics tab).'
    tech_done_rebuild = 'Components installed. Only one rebuild of the game is left (Rebuild the game button) to turn DLSS on.'
    tech_fail = 'Some options were not installed. The game opens without them.'
    safe = 'Safe mode (play without extra technologies)'
    safe_on = 'On: the game opens without DLSS, FSR 4 and Streamline, only with its own upscaler and frame generation.'
    safe_off = 'Off. Turn it on if the game crashes, to test without the technologies above.'
    help_tech = 'The launcher detects your GPU and only offers what it supports. Inside the game (Insert menu, Graphics tab) you pick the upscaler and the frame generation method.'
    badge_ok = 'On'
    badge_off = 'Not included'
    badge_todo = 'Needs install'
    badge_no = 'Not supported'
    badge_exp = 'Experimental'
    badge_safe = 'Safe mode'
    tn_dsr = 'NVIDIA DLSS (upscaling and DLAA)'
    tn_dlss = 'NVIDIA DLSS Frame Generation'
    tn_fsr = 'AMD FSR 4'
    tech_intro = 'Everything your GPU supports is on. Then just pick inside the game (Insert menu, Graphics tab): the Upscaler and the frame generation method.'
    st_dsr_on = 'On. In the game, the Upscaler row picks DLSS or DLAA.'
    st_dsr_todo = 'Turned on at the next rebuild of the game (once; the launcher handles it).'
    st_dlss_on = 'On. In the game, the Frame generation method row picks DLSS and the Frame generation row the multiplier.'
    st_dlss_todo = 'The NVIDIA components (about 276 MB) are downloaded once, when you click Play or Install everything.'
    st_fsr_on = 'On. In the game, the Upscaler row picks FSR 4.'
    st_fsr_rebuild = 'Turned on at the next rebuild of the game (once).'
    st_fsr_todo = 'The FSR 4 component (about 14 MB) is downloaded once, when you click Play or Install everything.'
    st_fsr_other = 'Made for AMD cards and not included on this card. The game''s own FSR 3.1 stays in the menu.'
    st_safe = 'Safe mode on: not used.'
    help_tune = 'Round 2: new ASTC textures stay provisional when loading goes over the per-frame limit. Try 120 ms or No deferral. Diagnostics log the unbound buffer to the log.'
    lbl_now = 'What is happening now'
    lbl_steps = 'Steps'
    lbl_next = 'Next step'
    lbl_notes = 'What you saw in the last match (saved with the log)'
    lbl_summary = 'Summary of the last round'
    summary_ph = 'Shows up here when you close the game.'
    st_err = 'Something went wrong'
    now_err = 'The build hit an error and may have stopped.'
    next_err = 'Click "Copy report for support" and paste it into the chat to get help.'
    st_ready = 'Ready to play'
    now_ready = 'The game was built and is installed on your PC.'
    next_ready = 'Click Play.'
    st_none = 'Not started yet'
    next_none = 'Click "Build the game".'
    st_build = 'Building the game'
    now_read = 'Copying your game files to the PC. This only uses the disk.'
    now_lift = 'Converting the Switch 2 code into PC code. This is a quick step.'
    now_compile = 'Turning that code into a program. This is the longest step and keeps the processor busy.'
    now_finish = 'Finishing: putting the pieces together and preparing the graphics effects.'
    now_shaders = 'Preparing the graphics effects (shaders) for your video card. It takes a few minutes, this time only.'
    st_shaders = 'Preparing the shaders'
    next_shaders = 'When it ends, the Play button turns on by itself. The build window closes by itself.'
    next_build = 'You do not need to do anything. Leave this window open and use the PC normally.'
    act_pre = 'Last activity '
    act_post = ' ago'
    eta_pre = 'About '
    eta_post = ' left'
    lt1 = 'less than 1 minute'
    s1 = '{0} 1. Read the game ({1:N0}%)'
    s2 = '{0} 2. Translate to PC ({1:N0}%)'
    s3 = '{0} 3. Build the program ({1:N0}%, {2} of {3} pieces)'
    s4 = '{0} 4. Finish and package ({1:N0}%)'
    q_build = 'Start building the game? It can take over an hour and uses the processor heavily.'
    e_script = 'Could not find the build script: {0}'
    e_script2 = 'Could not find the script: {0}'
    nup_use = 'Use this game file?{n}{n}{0}{n}{n}Yes = use it.   No = choose another file.'
    nup_title = 'Choose your Zelda Ocarina of Time game file (.nup)'
    nup_filter = 'Game file (*.nup)|*.nup|All files|*.*'
    nup_none = 'The build cannot start without the game file (.nup).'
    rep_copied = 'Report copied. Paste it into the chat with Ctrl+V.'
    started = 'Game started. When you close it, this round''s log is saved in the launcher''s rodadas folder.'
    saved = 'Round saved: {0}'
}

function T([string]$k) {
    $v = $null
    if ($STR.ContainsKey($script:lang)) { $v = $STR[$script:lang][$k] }
    if ($null -eq $v) { $v = $STR['pt'][$k] }
    if ($null -eq $v) { return $k }
    return ([string]$v).Replace('{n}', "`n")
}

# ---------- Perfis de jogos ----------
if (-not (Test-Path $ProfilesPath)) {
    $default = @{ games = @(
        @{
            id          = 'zelda-oot'
            name        = 'Zelda: Ocarina of Time'
            subtitle    = 'Switch 2, recompilado para PC'
            logPath     = (Join-Path $AppDir 'build.log')
            workDir     = (Join-Path $AppDir 'build-work')
            outDir      = 'C:\Games\RecompZel'
            buildScript = (Join-Path $PSScriptRoot 'build-game.ps1')
            totalFiles  = 186583
            needs       = 'Voce precisa do seu proprio arquivo do jogo (.nup). Nada e baixado da internet.'
        }
    ) }
    $default | ConvertTo-Json -Depth 6 | Set-Content $ProfilesPath -Encoding UTF8
}
$games = @((Get-Content $ProfilesPath -Raw | ConvertFrom-Json).games)
$script:g = $games[0]

# A pasta do jogo: o nome novo (RecompZel) se existir, senao o antigo (HookshotDev), senao o novo (sera criado pelo build)
function Get-OutDir {
    $p = [string]$script:g.outDir
    if ([string]::IsNullOrEmpty($p)) { return $p }
    $new = $p -replace 'HookshotDev$', 'RecompZel'
    $old = $p -replace 'RecompZel$', 'HookshotDev'
    if (Test-Path -LiteralPath $new) { return $new }
    if (Test-Path -LiteralPath $old) { return $old }
    return $new
}

$xaml = @'
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        Title="RecompZel" Width="860" Height="960" ResizeMode="CanMinimize"
        WindowStartupLocation="CenterScreen" Background="#0E1714" FontFamily="Segoe UI">
  <Window.Resources>
    <Style x:Key="Row" TargetType="Button">
      <Setter Property="Foreground" Value="#E6F2EC"/>
      <Setter Property="FontSize" Value="15"/>
      <Setter Property="Height" Value="48"/>
      <Setter Property="Margin" Value="0,0,0,8"/>
      <Setter Property="Cursor" Value="Hand"/>
      <Setter Property="Template">
        <Setter.Value>
          <ControlTemplate TargetType="Button">
            <Border x:Name="bd" Background="#1B2A25" BorderBrush="#2E4A40" BorderThickness="1" CornerRadius="3" Padding="16,0">
              <TextBlock Text="{TemplateBinding Content}" VerticalAlignment="Center"/>
            </Border>
            <ControlTemplate.Triggers>
              <Trigger Property="IsMouseOver" Value="True">
                <Setter TargetName="bd" Property="Background" Value="#27413A"/>
                <Setter TargetName="bd" Property="BorderBrush" Value="#6FD3A0"/>
              </Trigger>
              <Trigger Property="IsEnabled" Value="False">
                <Setter TargetName="bd" Property="Opacity" Value="0.4"/>
              </Trigger>
            </ControlTemplate.Triggers>
          </ControlTemplate>
        </Setter.Value>
      </Setter>
    </Style>
  </Window.Resources>
  <Grid Margin="20">
    <Grid.ColumnDefinitions>
      <ColumnDefinition Width="300"/>
      <ColumnDefinition Width="20"/>
      <ColumnDefinition Width="*"/>
    </Grid.ColumnDefinitions>

    <ScrollViewer Grid.Column="0" VerticalScrollBarVisibility="Auto">
    <StackPanel Margin="0,0,8,0">
      <DockPanel>
        <ComboBox x:Name="cbLang" DockPanel.Dock="Right" Width="124" Height="24" VerticalAlignment="Center"/>
        <TextBlock Text="RecompZel" Foreground="#6FD3A0" FontSize="26" FontWeight="SemiBold"/>
      </DockPanel>
      <TextBlock x:Name="txtGameSub" Foreground="#8FA89C" FontSize="12" Margin="0,0,0,10" TextWrapping="Wrap"/>
      <ComboBox x:Name="cbGame" Height="28" Margin="0,0,0,12"/>
      <Button x:Name="btnPlay" Style="{StaticResource Row}" Height="64" FontSize="19"/>
      <Button x:Name="btnBuild" Style="{StaticResource Row}"/>
      <Button x:Name="btnFolder" Style="{StaticResource Row}"/>
      <Button x:Name="btnReport" Style="{StaticResource Row}"/>
      <Button x:Name="btnUpdate" Style="{StaticResource Row}"/>
      <Border x:Name="vramBox" Background="#1B2A25" BorderBrush="#2E4A40" BorderThickness="1" CornerRadius="3" Padding="16,10">
        <StackPanel>
          <TextBlock x:Name="txtVramT" Foreground="#E6F2EC" FontSize="13"/>
          <ComboBox x:Name="cbVram" Margin="0,6,0,0" Height="26"/>
        </StackPanel>
      </Border>
      <Border x:Name="meshBox" Background="#1B2A25" BorderBrush="#2E4A40" BorderThickness="1" CornerRadius="3" Padding="16,10" Margin="0,8,0,0">
        <StackPanel>
          <TextBlock x:Name="txtMeshT" Foreground="#E6F2EC" FontSize="13"/>
          <ComboBox x:Name="cbMesh" Margin="0,6,0,0" Height="26"/>
          <TextBlock x:Name="txtMesh" Foreground="#8FA89C" FontSize="11" TextWrapping="Wrap" Margin="0,4,0,0"/>
        </StackPanel>
      </Border>
      <Border x:Name="tuneBox" Background="#1B2A25" BorderBrush="#2E4A40" BorderThickness="1" CornerRadius="3" Padding="16,10" Margin="0,8,0,0">
        <StackPanel>
          <TextBlock x:Name="txtMemT" Foreground="#E6F2EC" FontSize="13"/>
          <ComboBox x:Name="cbMem" Margin="0,6,0,8" Height="26"/>
          <TextBlock x:Name="txtUpT" Foreground="#E6F2EC" FontSize="13"/>
          <ComboBox x:Name="cbUpload" Margin="0,6,0,8" Height="26"/>
          <TextBlock x:Name="txtFgT" Foreground="#E6F2EC" FontSize="13"/>
          <ComboBox x:Name="cbFg" Margin="0,6,0,8" Height="26"/>
          <CheckBox x:Name="chkRam" Foreground="#E6F2EC" FontSize="12" Margin="0,0,0,6"/>
          <CheckBox x:Name="chkDiag" Foreground="#E6F2EC" FontSize="12"/>
        </StackPanel>
      </Border>
      <Border x:Name="techBox" Background="#1B2A25" BorderBrush="#2E4A40" BorderThickness="1" CornerRadius="3" Padding="14,10" Margin="0,8,0,0">
        <StackPanel>
          <TextBlock x:Name="txtTechT" Foreground="#6FD3A0" FontSize="14" FontWeight="SemiBold"/>
          <TextBlock x:Name="txtGpu" Foreground="#8FA89C" FontSize="11" TextWrapping="Wrap" Margin="0,2,0,4"/>
          <TextBlock x:Name="txtTechIntro" Foreground="#E6F2EC" FontSize="11" TextWrapping="Wrap" Margin="0,2,0,2"/>
          <Border Background="#14201C" BorderBrush="#2E4A40" BorderThickness="1" CornerRadius="3" Padding="10,8" Margin="0,6,0,0">
            <StackPanel>
              <DockPanel>
                <TextBlock x:Name="badgeDsr" DockPanel.Dock="Right" FontSize="10" FontWeight="SemiBold" VerticalAlignment="Center" Margin="6,0,0,0"/>
                <CheckBox x:Name="chkDsr" Visibility="Collapsed"/>
                <TextBlock x:Name="ttlDsr" Foreground="#E6F2EC" FontSize="12"/>
              </DockPanel>
              <TextBlock x:Name="txtDsr" Foreground="#8FA89C" FontSize="11" TextWrapping="Wrap" Margin="20,2,0,0"/>
            </StackPanel>
          </Border>
          <Border Background="#14201C" BorderBrush="#2E4A40" BorderThickness="1" CornerRadius="3" Padding="10,8" Margin="0,6,0,0">
            <StackPanel>
              <DockPanel>
                <TextBlock x:Name="badgeDlss" DockPanel.Dock="Right" FontSize="10" FontWeight="SemiBold" VerticalAlignment="Center" Margin="6,0,0,0"/>
                <CheckBox x:Name="chkDlss" Visibility="Collapsed"/>
                <TextBlock x:Name="ttlDlss" Foreground="#E6F2EC" FontSize="12"/>
              </DockPanel>
              <TextBlock x:Name="txtDlss" Foreground="#8FA89C" FontSize="11" TextWrapping="Wrap" Margin="20,2,0,0"/>
            </StackPanel>
          </Border>
          <Border Background="#14201C" BorderBrush="#2E4A40" BorderThickness="1" CornerRadius="3" Padding="10,8" Margin="0,6,0,0">
            <StackPanel>
              <DockPanel>
                <TextBlock x:Name="badgeFsr" DockPanel.Dock="Right" FontSize="10" FontWeight="SemiBold" VerticalAlignment="Center" Margin="6,0,0,0"/>
                <CheckBox x:Name="chkFsr" Visibility="Collapsed"/>
                <TextBlock x:Name="ttlFsr" Foreground="#E6F2EC" FontSize="12"/>
              </DockPanel>
              <TextBlock x:Name="txtFsr" Foreground="#8FA89C" FontSize="11" TextWrapping="Wrap" Margin="20,2,0,0"/>
            </StackPanel>
          </Border>
          <Button x:Name="btnTechAll" Style="{StaticResource Row}" Height="40" FontSize="12" Margin="0,10,0,0"/>
          <CheckBox x:Name="chkSafe" Foreground="#E6F2EC" FontSize="12" Margin="0,2,0,0"/>
          <TextBlock x:Name="txtSafe" Foreground="#8FA89C" FontSize="11" TextWrapping="Wrap" Margin="20,2,0,0"/>
        </StackPanel>
      </Border>
    </StackPanel>
    </ScrollViewer>

    <Border Grid.Column="2" Background="#14201C" BorderBrush="#2E4A40" BorderThickness="1" CornerRadius="3" Padding="22">
      <StackPanel>
        <TextBlock x:Name="txtGame" Foreground="#E6F2EC" FontSize="15" FontWeight="SemiBold"/>
        <TextBlock x:Name="txtPct" Text="0%" Foreground="#FFFFFF" FontSize="60" FontWeight="Bold"/>
        <ProgressBar x:Name="pbTotal" Height="14" Minimum="0" Maximum="100" Value="0"
                     Foreground="#6FD3A0" Background="#0E1714" BorderThickness="0"/>
        <TextBlock x:Name="txtStatus" Foreground="#6FD3A0" FontSize="14" FontWeight="SemiBold" Margin="0,8,0,2"/>
        <TextBlock x:Name="txtTime" Foreground="#8FA89C" FontSize="12" Margin="0,0,0,14"/>

        <TextBlock x:Name="lblNow" Foreground="#8FA89C" FontSize="12"/>
        <TextBlock x:Name="txtNow" Foreground="#E6F2EC" FontSize="14" TextWrapping="Wrap" Margin="0,2,0,14"/>

        <TextBlock x:Name="lblSteps" Foreground="#8FA89C" FontSize="12" Margin="0,0,0,4"/>
        <TextBlock x:Name="txtS1" Foreground="#E6F2EC" FontSize="14" Margin="0,0,0,5"/>
        <TextBlock x:Name="txtS2" Foreground="#E6F2EC" FontSize="14" Margin="0,0,0,5"/>
        <TextBlock x:Name="txtS3" Foreground="#E6F2EC" FontSize="14" Margin="0,0,0,5"/>
        <TextBlock x:Name="txtS4" Foreground="#E6F2EC" FontSize="14" Margin="0,0,0,14"/>

        <TextBlock x:Name="lblNext" Foreground="#8FA89C" FontSize="12"/>
        <TextBlock x:Name="txtNext" Foreground="#E6F2EC" FontSize="14" TextWrapping="Wrap" Margin="0,2,0,14"/>

        <TextBlock x:Name="lblNotes" Foreground="#8FA89C" FontSize="12"/>
        <TextBox x:Name="txtNotas" Height="56" AcceptsReturn="True" TextWrapping="Wrap" Margin="0,4,0,12"
                 Background="#0E1714" Foreground="#E6F2EC" BorderBrush="#2E4A40" CaretBrush="#E6F2EC" FontSize="13"/>

        <TextBlock x:Name="lblSummary" Foreground="#8FA89C" FontSize="12"/>
        <TextBlock x:Name="txtResumo" Foreground="#E6F2EC" FontSize="12" TextWrapping="Wrap" Margin="0,2,0,12"/>

        <TextBlock x:Name="txtHelp" Foreground="#6E857A" FontSize="12" TextWrapping="Wrap"/>
      </StackPanel>
    </Border>
  </Grid>
</Window>
'@

$reader = New-Object System.Xml.XmlNodeReader ([xml]$xaml)
$win = [Windows.Markup.XamlReader]::Load($reader)
try { if (Test-Path (Join-Path $PSScriptRoot 'recompzel.ico')) { $win.Icon = [Windows.Media.Imaging.BitmapFrame]::Create([Uri](Join-Path $PSScriptRoot 'recompzel.ico')) } } catch {}
foreach ($n in 'cbLang','btnPlay','btnBuild','btnFolder','btnReport','btnUpdate','cbMem','txtMemT','cbVram','cbMesh','cbGame','txtGameSub','txtGame','txtPct','pbTotal','txtStatus','txtTime','txtNow','txtNext','txtS1','txtS2','txtS3','txtS4','txtHelp','vramBox','meshBox','tuneBox','cbUpload','chkRam','chkDiag','cbFg','txtNotas','txtResumo','chkFsr','txtFsr','techBox','txtTechT','txtGpu','badgeDsr','badgeDlss','badgeFsr','btnTechAll','chkSafe','txtSafe','ttlDsr','ttlDlss','ttlFsr','txtTechIntro','chkDlss','txtDlss','chkDsr','txtDsr','txtVramT','txtMeshT','txtMesh','txtUpT','txtFgT','lblNow','lblSteps','lblNext','lblNotes','lblSummary') {
    Set-Variable -Name $n -Value $win.FindName($n)
}
$script:defaultHelp = ''

# ---------- Opcoes (a ordem e o indice salvo em launcher-settings.json: nao reordenar) ----------
$vramOptions = @(
    @{ Key = 'vram_d'; Pt = 'Padrao do jogo (70% da VRAM, ate 6 GB)'; Mb = 0 },
    @{ Key = '';       Pt = '8 GB';  Mb = 8192 },
    @{ Key = '';       Pt = '10 GB'; Mb = 10240 },
    @{ Key = '';       Pt = '12 GB'; Mb = 12288 },
    @{ Key = '';       Pt = '6 GB (economiza VRAM)'; Mb = 6144 },
    @{ Key = '';       Pt = '5 GB (economiza VRAM)'; Mb = 5120 },
    @{ Key = '';       Pt = '4 GB (economiza VRAM)'; Mb = 4096 },
    @{ Key = '';       Pt = '3 GB (economiza VRAM, texturas podem recarregar)'; Mb = 3072 }
)
# Perfil de memoria: junta as opcoes de economia num clique (o 'Padrao' nao muda nada e as caixas e o limite de VRAM abaixo continuam valendo).
# Os valores sao conservadores e ainda estao sendo ajustados com medidas reais (Jogo agora: RAM/VRAM na linha de status).
#   Vram = RX_VK_VRAM_MB (orcamento de texturas), Mirror = RX_VK_MIRROR_MB (copia da memoria do console na VRAM),
#   Pool = RX_VK_TARGET_POOL_MB (alvos de renderizacao guardados), Tex = RX_VK_TEX_MAX_MB (maior textura), PCache = sem cache de pipelines
$memProfiles = @(
    @{ Key = '';  Pt = 'Padrao do jogo'; Vram = 0; Mirror = 0; Pool = 0; Tex = 0; PCache = $false },
    @{ Key = '';  Pt = 'Equilibrado (economiza uns 1 a 2 GB)'; Vram = 6144; Mirror = 1536; Pool = 128; Tex = 0; PCache = $true },
    @{ Key = '';  Pt = 'Economico (menos RAM e VRAM, pode recarregar texturas)'; Vram = 4096; Mirror = 1024; Pool = 64; Tex = 768; PCache = $true }
)
# Upload de texturas (RX_VK_UPLOAD_BUDGET_MS): 40 ms e o padrao do jogo; 0 = sem adiamento
$uploadOptions = @(
    @{ Key = 'up_0'; Pt = 'Padrao do jogo (40 ms)'; Ms = -1 },
    @{ Key = 'up_1'; Pt = '120 ms'; Ms = 120 },
    @{ Key = 'up_2'; Pt = 'Sem adiamento (0 ms)'; Ms = 0 }
)
# Metodo de geracao de quadros: o do RecompZel (padrao), o FSR 3.1 (RX_VK_FSR_FG=1, so 2x) ou desligado
$fgOptions = @(
    @{ Key = 'fg_0'; Pt = 'RecompZel (padrao, 2x a 8x)'; Fsr = $false; Off = $false },
    @{ Key = 'fg_1'; Pt = 'AMD FSR 3.1 (so 2x)'; Fsr = $true; Off = $false },
    @{ Key = 'fg_2'; Pt = 'Desligado (sem geracao de quadros)'; Fsr = $false; Off = $true }
)
# mesh_shaders no hookshot_options.ini: 0 automatico, 1 nativo, 2 compute
$meshKeys = @('mesh_0', 'mesh_1', 'mesh_2')

function Opt-Label($o) {
    if ($o.Key) { return (T $o.Key) }
    return [string]$o.Pt
}
function Fill-Combo($cb, $labels) {
    $i = $cb.SelectedIndex
    $cb.Items.Clear()
    foreach ($l in $labels) { [void]$cb.Items.Add([string]$l) }
    if ($i -lt 0 -or $i -ge $cb.Items.Count) { $i = 0 }
    $cb.SelectedIndex = $i
}

# ---------- Aplica o idioma a todos os textos fixos ----------
function Apply-Language {
    $script:loading = $true
    try {
        $btnPlay.Content = T 'play';   $btnPlay.Tag = T 'play_tip'
        $btnFolder.Content = T 'folder'; $btnFolder.Tag = T 'folder_tip'
        $btnReport.Content = T 'report'; $btnReport.Tag = T 'report_tip'
        if ($script:updateAvail) { $btnUpdate.Content = T 'upd_avail' } else { $btnUpdate.Content = T 'upd' }
        $btnUpdate.Tag = T 'upd_tip'
        $btnBuild.Tag = T 'build_tip'
        $txtVramT.Text = T 'vram_t'; $txtMeshT.Text = T 'mesh_t'; $txtUpT.Text = T 'up_t'; $txtMemT.Text = T 'mem_t'; $txtFgT.Text = T 'fg_t'
        $tbRam = New-Object System.Windows.Controls.TextBlock; $tbRam.Text = (T 'ram_save'); $tbRam.TextWrapping = 'Wrap'; $chkRam.Content = $tbRam; $chkRam.ToolTip = (T 'ram_tip')
        $chkDiag.Content = T 'diag'; $chkFsr.Content = T 'fsr'; $chkDlss.Content = T 'dlss'; $chkDsr.Content = T 'dsr'
        $txtTechT.Text = T 'tech_t'; $txtTechIntro.Text = T 'tech_intro'; $ttlDsr.Text = T 'tn_dsr'; $ttlDlss.Text = T 'tn_dlss'; $ttlFsr.Text = T 'tn_fsr'; $btnTechAll.Content = T 'tech_all'; $chkSafe.Content = T 'safe'
        $lblNow.Text = T 'lbl_now'; $lblSteps.Text = T 'lbl_steps'; $lblNext.Text = T 'lbl_next'
        $lblNotes.Text = T 'lbl_notes'; $lblSummary.Text = T 'lbl_summary'
        if ($txtResumo.Tag -ne 'real') { $txtResumo.Text = T 'summary_ph' }
        Fill-Combo $cbVram (@($vramOptions | ForEach-Object { Opt-Label $_ }))
        Fill-Combo $cbUpload (@($uploadOptions | ForEach-Object { Opt-Label $_ }))
        Fill-Combo $cbMem (@($memProfiles | ForEach-Object { Opt-Label $_ }))
        Fill-Combo $cbFg (@($fgOptions | ForEach-Object { Opt-Label $_ }))
        Fill-Combo $cbMesh (@($meshKeys | ForEach-Object { T $_ }))
        $script:defaultHelp = T 'help'
        $txtHelp.Text = $script:defaultHelp
    } finally { $script:loading = $false }
}

foreach ($x in $games) { [void]$cbGame.Items.Add([string]$x.name) }
$cbGame.SelectedIndex = 0
if ($games.Count -le 1) { $cbGame.Visibility = 'Collapsed' }
[void]$cbLang.Items.Add('Portugues (BR)')
[void]$cbLang.Items.Add('English')
$cbLang.SelectedIndex = 0
$script:obs0 = $null; $script:obsT0 = $null

# ---------- Configuracoes salvas ----------
Apply-Language   # (primeiro com o idioma padrao: enche as listas, para os indices salvos abaixo terem onde cair)
$script:loading = $true
try {
    if (Test-Path $Cfg) {
        $c = Get-Content $Cfg -Raw | ConvertFrom-Json
        if ($c.lang -eq 'en') { $script:lang = 'en'; $cbLang.SelectedIndex = 1 }
        if ($c.vramIndex -ge 0 -and $c.vramIndex -lt $vramOptions.Count) { $cbVram.SelectedIndex = [int]$c.vramIndex }
        if ($c.uploadIndex -ge 0 -and $c.uploadIndex -lt $uploadOptions.Count) { $cbUpload.SelectedIndex = [int]$c.uploadIndex }
        if ($c.memIndex -ge 0 -and $c.memIndex -lt $memProfiles.Count) { $cbMem.SelectedIndex = [int]$c.memIndex }
        if ($c.diag -eq $true) { $chkDiag.IsChecked = $true }
        if ($c.ramSave -eq $true) { $chkRam.IsChecked = $true }
        if ($c.fsr -eq $true) { $chkFsr.IsChecked = $true }
        if ($c.dlss -eq $true) { $chkDlss.IsChecked = $true }
        if ($c.dsr -eq $true) { $chkDsr.IsChecked = $true }
        if ($c.safe -eq $true) { $chkSafe.IsChecked = $true }
        if ($c.fgIndex -ge 0 -and $c.fgIndex -lt $fgOptions.Count) { $cbFg.SelectedIndex = [int]$c.fgIndex }
    }
} catch {}
$script:loading = $false
Apply-Language
$cbFg.SelectedIndex = 0; $txtFgT.Visibility = 'Collapsed'; $cbFg.Visibility = 'Collapsed'   # (o metodo e o multiplicador ficam no menu do jogo)

function Save-Settings {
    if ($script:loading) { return }
    try {
        @{ vramIndex = $cbVram.SelectedIndex; uploadIndex = $cbUpload.SelectedIndex; memIndex = $cbMem.SelectedIndex; fgIndex = $cbFg.SelectedIndex; diag = [bool]$chkDiag.IsChecked; ramSave = [bool]$chkRam.IsChecked; fsr = [bool]$chkFsr.IsChecked; dlss = [bool]$chkDlss.IsChecked; dsr = [bool]$chkDsr.IsChecked; safe = [bool]$chkSafe.IsChecked; lang = $script:lang } |
            ConvertTo-Json | Set-Content $Cfg -Encoding ASCII
    } catch {}
}

# ---------- Mesh shaders: le e grava mesh_shaders= no hookshot_options.ini da pasta do jogo ----------
function Get-IniPath { return (Join-Path (Get-OutDir) 'hookshot_options.ini') }
function Test-GameRunning {
    if ($script:gameProc) { try { if (-not $script:gameProc.HasExited) { return $true } } catch {} }
    return [bool](Get-Process -Name 'RecompZel', 'hookshot' -ErrorAction SilentlyContinue)
}
function Set-DsrChoice([bool]$on) {
    # dlss= no hookshot_options.ini: 0 jogo, 1 DLSS, 2 DLAA. Marcada: so sai do 0 (mantem a escolha do menu, DLSS ou DLAA); desmarcada: volta ao 0
    $p = Get-IniPath
    if (-not (Test-Path -LiteralPath $p) -or (Test-GameRunning)) { return }
    try {
        $raw = [IO.File]::ReadAllText($p)
        $cur = 0
        if ($raw -match '(?m)^\s*dlss\s*=\s*(\d+)') { $cur = [int]$Matches[1] }
        $want = $cur
        if ($on -and $cur -lt 1) { $want = 1 } elseif ((-not $on) -and $cur -ge 1 -and $cur -le 2) { $want = 0 }
        if ($want -eq $cur) { return }
        if ($raw -match '(?m)^\s*dlss\s*=') { $new = [regex]::Replace($raw, '(?m)^(\s*dlss\s*=\s*)\d+', ('${1}' + $want)) }
        else { $nl = if ($raw.Contains("`r`n")) { "`r`n" } else { "`n" }; if (-not $raw.EndsWith("`n")) { $raw += $nl }; $new = $raw + 'dlss=' + $want + $nl }
        [IO.File]::WriteAllText($p, $new)
    } catch {}
}
function Get-IniInt([string]$key, [int]$default) {
    $p = Get-IniPath
    if (-not (Test-Path -LiteralPath $p)) { return $default }
    try { foreach ($l in [IO.File]::ReadAllLines($p)) { if ($l -match ('^\s*' + [regex]::Escape($key) + '\s*=\s*(\d+)')) { return [int]$Matches[1] } } } catch {}
    return $default
}
function Set-IniInt([string]$key, [int]$val) {
    $p = Get-IniPath
    if (-not (Test-Path -LiteralPath $p) -or (Test-GameRunning)) { return }
    try {
        $raw = [IO.File]::ReadAllText($p)
        if ($raw -match ('(?m)^\s*' + [regex]::Escape($key) + '\s*=')) { $new = [regex]::Replace($raw, ('(?m)^(\s*' + [regex]::Escape($key) + '\s*=\s*)\d+'), ('${1}' + $val)) }
        else { $nl = if ($raw.Contains("`r`n")) { "`r`n" } else { "`n" }; if (-not $raw.EndsWith("`n")) { $raw += $nl }; $new = $raw + $key + '=' + $val + $nl }
        [IO.File]::WriteAllText($p, $new)
    } catch {}
}
# Ao marcar a caixa do DLSS Frame Generation: metodo DLSS e pelo menos 2x no menu do jogo (frame_generation_method, frame_generation); ao desmarcar, volta ao metodo do RecompZel
function Set-FgChoice([bool]$on) {
    if ($on) {
        Set-IniInt 'frame_generation_method' 1
        if ((Get-IniInt 'frame_generation' 0) -lt 2) { Set-IniInt 'frame_generation' 2 }
    } elseif ((Get-IniInt 'frame_generation_method' 0) -eq 1) { Set-IniInt 'frame_generation_method' 0 }
}
function Read-Mesh {
    $p = Get-IniPath
    if (-not (Test-Path -LiteralPath $p)) { return $null }
    try {
        foreach ($l in [IO.File]::ReadAllLines($p)) {
            if ($l -match '^\s*mesh_shaders\s*=\s*(\d+)\s*$') { return [int]$Matches[1] }
        }
    } catch { return $null }
    return 0
}
function Set-Mesh([int]$v) {
    $p = Get-IniPath
    if (-not (Test-Path -LiteralPath $p)) { $txtMesh.Text = T 'mesh_noini'; return $false }
    if (Test-GameRunning) { $txtMesh.Text = T 'mesh_close'; return $false }
    try {
        $raw = [IO.File]::ReadAllText($p)
        Copy-Item -LiteralPath $p -Destination ($p + '.bak') -Force
        if ($raw -match '(?m)^\s*mesh_shaders\s*=') {
            $new = [regex]::Replace($raw, '(?m)^(\s*mesh_shaders\s*=\s*)\d+', ('${1}' + $v))
        } else {
            $nl = if ($raw.Contains("`r`n")) { "`r`n" } else { "`n" }
            if (-not ($raw.EndsWith("`n"))) { $raw += $nl }
            $new = $raw + 'mesh_shaders=' + $v + $nl
        }
        [IO.File]::WriteAllText($p, $new, (New-Object System.Text.UTF8Encoding($false)))
        return $true
    } catch {
        $txtMesh.Text = ((T 'mesh_fail') -f $_.Exception.Message)
        return $false
    }
}
function Refresh-Mesh {
    $cur = Read-Mesh
    $script:loading = $true
    try {
        if ($null -eq $cur) {
            $cbMesh.IsEnabled = $false
            $txtMesh.Text = T 'mesh_noini'
        } else {
            $cbMesh.IsEnabled = $true
            if ($cur -ge 0 -and $cur -lt $cbMesh.Items.Count) { $cbMesh.SelectedIndex = $cur }
            $txtMesh.Text = T 'mesh_ok'
        }
    } finally { $script:loading = $false }
}
$cbMesh.Add_SelectionChanged({
    if ($script:loading) { return }
    $cur = Read-Mesh
    $want = $cbMesh.SelectedIndex
    if ($null -ne $cur -and $cur -eq $want) { return }
    if (Set-Mesh $want) { $txtMesh.Text = T 'mesh_saved' }
    else {
        $script:loading = $true
        try { if ($null -ne $cur) { $cbMesh.SelectedIndex = $cur } } finally { $script:loading = $false }
    }
})

$cbGame.Add_SelectionChanged({
    $script:g = $games[$cbGame.SelectedIndex]
    $script:obs0 = $null; $script:obsT0 = $null; $script:lastCountTime = [datetime]::MinValue
    Update-View
    Refresh-Mesh
})
$cbVram.Add_SelectionChanged({ Save-Settings })
$cbUpload.Add_SelectionChanged({ Save-Settings })
$cbMem.Add_SelectionChanged({ Save-Settings })
$cbFg.Add_SelectionChanged({ Save-Settings })
$chkDiag.Add_Click({ Save-Settings })
$chkRam.Add_Click({ Save-Settings })
$chkFsr.Add_Click({ Save-Settings; Update-Fsr-Text; Update-Tech })
$chkDlss.Add_Click({ Save-Settings; Set-FgChoice ([bool]$chkDlss.IsChecked); Update-Dlss-Text; Update-Tech })
$chkDsr.Add_Click({ Save-Settings; Update-Dsr-Text; Update-Tech })
$chkSafe.Add_Click({ Save-Settings; Update-Tech })
$cbLang.Add_SelectionChanged({
    if ($script:loading) { return }
    if ($cbLang.SelectedIndex -eq 1) { $script:lang = 'en' } else { $script:lang = 'pt' }
    Apply-Language
    Save-Settings
    Update-View
    Update-Tech
    Refresh-Mesh
})

# ---------- Ajuda ao passar o mouse ----------
foreach ($b in @($btnPlay, $btnBuild, $btnFolder, $btnReport, $btnUpdate)) {
    $b.Add_MouseEnter({ param($s, $e) $txtHelp.Text = [string]$s.Tag })
    $b.Add_MouseLeave({ $txtHelp.Text = $script:defaultHelp })
}
$vramBox.Add_MouseEnter({ $txtHelp.Text = T 'vram_tip' })
$vramBox.Add_MouseLeave({ $txtHelp.Text = $script:defaultHelp })
$meshBox.Add_MouseEnter({ $txtHelp.Text = T 'mesh_tip' })
$meshBox.Add_MouseLeave({ $txtHelp.Text = $script:defaultHelp })
$tuneBox.Add_MouseEnter({ $txtHelp.Text = T 'help_tune' })
$tuneBox.Add_MouseLeave({ $txtHelp.Text = $script:defaultHelp })
$techBox.Add_MouseEnter({ $txtHelp.Text = T 'help_tech' })
$techBox.Add_MouseLeave({ $txtHelp.Text = $script:defaultHelp })

# ---------- Leitura do log ----------
$script:lastCount = 0
$script:lastCountTime = [datetime]::MinValue
$script:lastObjTime = $null
$script:lastErrLines = @()

function Read-LogLines {
    $p = [string]$script:g.logPath
    if (-not (Test-Path $p)) { return @() }
    try {
        # economia: se o log nao mudou desde a ultima leitura (mesmo tamanho e hora), devolve o que ja leu
        $fi = Get-Item -LiteralPath $p
        $key = ('{0}|{1}|{2}' -f $p, $fi.Length, $fi.LastWriteTimeUtc.Ticks)
        if ($script:logKey -eq $key -and $null -ne $script:logLines) { return $script:logLines }
        $fs = [System.IO.File]::Open($p, 'Open', 'Read', 'ReadWrite')
        $sr = New-Object System.IO.StreamReader($fs)
        $txt = $sr.ReadToEnd(); $sr.Close(); $fs.Close()
        $script:logLines = $txt -split "`r?`n"; $script:logKey = $key
        return $script:logLines
    } catch { return @() }
}

function Find-GameExe {
    $o = Get-OutDir
    if (-not (Test-Path $o)) { return $null }
    $own = Join-Path $o 'RecompZel.exe'
    if (Test-Path -LiteralPath $own) { return Get-Item -LiteralPath $own }
    return Get-ChildItem -Path $o -Filter *.exe -File -ErrorAction SilentlyContinue | Select-Object -First 1
}

# ---------- Atalhos: cria os que faltam e garante o icone do RecompZel e o exe novo (roda ao abrir o launcher) ----------
function Update-Shortcuts {
    try {
        $ico = Join-Path $PSScriptRoot 'recompzel.ico'
        $iconOk = Test-Path -LiteralPath $ico
        $desk = [Environment]::GetFolderPath('Desktop')
        $sh = New-Object -ComObject WScript.Shell
        $changed = $false
        $ps = Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'
        foreach ($isGame in @($true, $false)) {
            if ($isGame) { $n = 'Zelda OoT (RecompZel).lnk' } else { $n = 'RecompZel Launcher.lnk' }
            $f = Join-Path $desk $n
            $exists = Test-Path -LiteralPath $f
            $exe = $null
            if ($isGame) { $exe = Find-GameExe; if (-not $exe) { continue } }
            $l = $sh.CreateShortcut($f)
            $dirty = $false
            if (-not $exists) {
                if ($isGame) { $l.Description = 'Zelda Ocarina of Time recompilado (RecompZel)' }
                else {
                    $l.TargetPath = $ps
                    $l.Arguments = ('-ExecutionPolicy Bypass -WindowStyle Hidden -File "' + (Join-Path $PSScriptRoot 'launcher.ps1') + '"')
                    $l.WorkingDirectory = $PSScriptRoot
                    $l.Description = 'Launcher do RecompZel'
                }
                $dirty = $true
            }
            if ($isGame -and $l.TargetPath -ne $exe.FullName) { $l.TargetPath = $exe.FullName; $l.WorkingDirectory = $exe.DirectoryName; $dirty = $true }
            if ($iconOk -and $l.IconLocation -ne ($ico + ',0')) { $l.IconLocation = $ico; $dirty = $true }
            if ($dirty) { $l.Save(); $changed = $true }
        }
        # o Windows guarda os icones em cache: pede para atualizar
        if ($changed) { Start-Process -FilePath 'ie4uinit.exe' -ArgumentList '-show' -WindowStyle Hidden }
    } catch {}
}

# ---------- AMD FSR 4 (opcional) ----------
# O jogo precisa ter sido construido com --fsr (marca .hookshot_fsr na pasta do jogo) e o componente fsr4vk precisa estar
# em <pasta do jogo>\fsr4vk. O componente e de terceiros (GPLv3), baixado uma vez do GitHub, e conferido por hash.
$Fsr4vkUrl  = 'https://github.com/0xCydral/bloodborne_pc/releases/download/windows-v1.7.0-beta.2/fsr4vk-v0.4.3-amdfix.zip'
$Fsr4vkSha  = '60a90b24f6789cd52c467471d5a66a0fa6d04e1b8af41095242f50367904f8b2'
$Fsr4vkName = 'amd_fidelityfx_upscaler_vk.dll'

function Get-FsrDir  { return (Join-Path (Get-OutDir) 'fsr4vk') }
function Test-FsrBuilt { return (Test-Path (Join-Path (Get-OutDir) '.hookshot_fsr')) }
function Test-FsrDll {
    $f = Join-Path (Get-FsrDir) $Fsr4vkName
    if (-not (Test-Path $f)) { return $false }
    try {
        # economia: o hash so e refeito quando o arquivo muda (e chamado a cada atualizacao da tela)
        $fi = Get-Item -LiteralPath $f
        $k = ('{0}|{1}' -f $fi.Length, $fi.LastWriteTimeUtc.Ticks)
        if ($script:fsrDllKey -ne $k) { $script:fsrDllKey = $k; $script:fsrDllOk = ((Get-FileHash -Path $f -Algorithm SHA256).Hash -ieq $Fsr4vkSha) }
        return $script:fsrDllOk
    } catch { return $false }
}

function Update-Fsr-Text { Update-Tech }   # (o painel Tecnologias de imagem cuida dos textos)

# ---------- NVIDIA DLSS, reescalonamento (opcional, RTX) ----------
# O motor ja tem o DLSS (gpu/vk/vk_dlss.cpp), mas so quando o jogo e construido com o SDK da NVIDIA (build-game.ps1 -Dlss) e o
# componente nvngx_dlss.dll fica em <pasta do jogo>\ngx. O SDK e o componente sao da NVIDIA (licenca NVIDIA RTX SDKs, so para placas
# NVIDIA): o build baixa e confere cada arquivo; nada disso fica no repositorio. a caixa so poe dlss=1 no hookshot_options.ini (o menu do jogo escolhe DLSS ou DLAA).
$script:dsrGpu = $null
function Test-DsrGpu {
    if ($null -ne $script:dsrGpu) { return $script:dsrGpu }
    try {
        $script:dsrGpu = $false
        foreach ($n in @(Get-CimInstance Win32_VideoController -ErrorAction Stop | ForEach-Object { [string]$_.Name })) {
            if ($n -match 'NVIDIA' -and $n -match 'RTX') { $script:dsrGpu = $true }
        }
    } catch { $script:dsrGpu = $true }
    return $script:dsrGpu
}
function Test-DsrBuilt { return (Test-Path (Join-Path (Get-OutDir) 'ngx\nvngx_dlss.dll')) }
function Update-Dsr-Text { Update-Tech }   # (o painel Tecnologias de imagem cuida dos textos)
# O arquivo do jogo (.nup): usa o ultimo escolhido ou o que achar em Downloads/Desktop/Documentos (pergunta antes) e senao abre a janela de escolher,
# na frente do launcher. Retorna o caminho ou $null se o usuario cancelou.
$NupMemo = Join-Path $AppDir 'nup-path.txt'
function Select-NupFile {
    $cand = $null
    try { if (Test-Path -LiteralPath $NupMemo) { $c = (Get-Content -LiteralPath $NupMemo -Raw).Trim(); if ($c -and (Test-Path -LiteralPath $c)) { $cand = $c } } } catch {}
    if (-not $cand) {
        $roots = @([Environment]::GetFolderPath('UserProfile') + '\Downloads', [Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('MyDocuments')) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }
        $all = @(); foreach ($r in $roots) { $all += @(Get-ChildItem -LiteralPath $r -Filter '*.nup' -File -Recurse -Depth 2 -ErrorAction SilentlyContinue) }
        $hit = $all | Where-Object { $_.Name -like '*0400486024DEC000*' } | Select-Object -First 1
        if (-not $hit) { $hit = $all | Sort-Object Length -Descending | Select-Object -First 1 }
        if ($hit) { $cand = $hit.FullName }
    }
    if ($cand) {
        if ([System.Windows.MessageBox]::Show($win, ((T 'nup_use') -f $cand), 'RecompZel', 'YesNo', 'Question') -eq 'Yes') { return $cand }
    }
    $dlg = New-Object Microsoft.Win32.OpenFileDialog
    $dlg.Title = T 'nup_title'
    $dlg.Filter = T 'nup_filter'
    $dlg.CheckFileExists = $true
    if ($cand) { $dlg.InitialDirectory = Split-Path $cand -Parent }
    if ($dlg.ShowDialog($win) -ne $true) { return $null }
    return $dlg.FileName
}
# Inicia o build: escolhe o .nup aqui no launcher e passa para o build-game.ps1 (-Nup), sem janela escondida atras
function Start-GameBuild([string]$buildPath) {
    $nup = Select-NupFile
    if (-not $nup) { [System.Windows.MessageBox]::Show($win, (T 'nup_none'), 'RecompZel') | Out-Null; return $false }
    try { Set-Content -LiteralPath $NupMemo -Value $nup -Encoding UTF8 } catch {}
    $script:obs0 = $null; $script:lastCountTime = [datetime]::MinValue
    $a = Get-BuildArgs $buildPath
    [Environment]::SetEnvironmentVariable('RZ_PAUSE', '1', 'Process')   # (build-game.ps1: a janela espera Enter so se der erro)
    $a += @('-Nup', ('"' + $nup + '"'))   # (aspas: o caminho pode ter espacos)
    Start-Process powershell.exe -ArgumentList $a
    return $true
}

# Os argumentos para abrir o build-game.ps1: com -Dlss quando a caixa do DLSS esta marcada
function Get-BuildArgs([string]$buildPath) {
    $a = @('-ExecutionPolicy', 'Bypass', '-File', ('"' + $buildPath + '"'))
    if ($chkDsr.IsChecked -and (Test-DsrGpu)) { $a += '-Dlss' }
    return $a
}

# ---------- NVIDIA DLSS Frame Generation (opcional, so RTX 40/50) ----------
# O motor (vk_streamline.cpp) carrega a Streamline da NVIDIA de <pasta do jogo>\streamline quando RX_VK_DLSSG=1. Os 6 arquivos
# sao da NVIDIA (Streamline 2.14.16, licenca NVIDIA RTX SDKs, so para placas NVIDIA): nao vao no repositorio. O launcher baixa o
# pacote oficial uma vez, extrai so eles e confere o hash de cada um.
$SlUrl = 'https://github.com/NVIDIA-RTX/Streamline/releases/download/v2.14.16/streamline-sdk-v2.14.16.zip'
$SlFiles = [ordered]@{
    'sl.interposer.dll' = 'b1d7395aebd7b9722841d64dcf7433680020b6a8e421f851c16d5ba0c2182edf'
    'sl.common.dll'     = '38eea3b4209afc455636ea372b5933d65fcc13becec6c84d101dcfc4d8648f75'
    'sl.dlss_g.dll'     = '3ed9538df724993bea8a050195a6a78b9c8c8a566d5b05ade477aab3c390e90f'
    'sl.pcl.dll'        = '5698c38e722318681f215c9fe68e45b9bedd51378acc699d8eee26e961e57770'
    'sl.reflex.dll'     = '443577e869352436ff7ec8f4d9c90418d3e95368436ce219261e0f4f07a38122'
    'nvngx_dlssg.dll'   = '8d59d49b36410dd6b62fef2503a5871d347415bd85d943fa0848563a95dd50c7'
}

# O DLSS (reescalonamento) e o Frame Generation precisam rodar juntos: a Streamline ja inicia o NGX da NVIDIA com a pasta streamline, entao o
# nvngx_dlss.dll (o mesmo arquivo do pacote da NVIDIA) precisa estar la tambem, senao o DLSS some do menu (FeatureInitResult 0xbad00004).
$SlSrName = 'nvngx_dlss.dll'
$SlSrSha  = 'd00b5b0ab29c3ca101b70c3a5ecb3a01b7ef33766a3383a28a18623083e6123e'
function Get-SlDir { return (Join-Path (Get-OutDir) 'streamline') }
# Copia o nvngx_dlss.dll do build com DLSS (pasta ngx) para a pasta streamline, conferindo o hash. Retorna $true quando ficou la.
function Ensure-SlSr {
    $dst = Join-Path (Get-SlDir) $SlSrName
    try {
        if ((Test-Path $dst) -and ((Get-FileHash -Path $dst -Algorithm SHA256).Hash -ieq $SlSrSha)) { return $true }
        $src = Join-Path (Get-OutDir) ('ngx\' + $SlSrName)
        if ((Test-Path $src) -and ((Get-FileHash -Path $src -Algorithm SHA256).Hash -ieq $SlSrSha)) {
            Copy-Item $src $dst -Force
            return $true
        }
    } catch {}
    return $false
}
$script:dlssGpu = $null
function Test-DlssGpu {
    if ($null -ne $script:dlssGpu) { return $script:dlssGpu }
    try {
        $names = @(Get-CimInstance Win32_VideoController -ErrorAction Stop | ForEach-Object { [string]$_.Name })
        $script:dlssGpu = $false
        foreach ($n in $names) { if ($n -match 'NVIDIA' -and $n -match 'RTX\s*[45]\d{3}') { $script:dlssGpu = $true } }
    } catch { $script:dlssGpu = $true }   # (nao deu para ler as placas: deixa tentar)
    return $script:dlssGpu
}
$script:dlssOk = $false; $script:dlssOkAt = [datetime]::MinValue
function Test-DlssFiles {
    if (([datetime]::Now - $script:dlssOkAt).TotalSeconds -lt 10) { return $script:dlssOk }
    $script:dlssOk = Test-DlssFilesNow; $script:dlssOkAt = [datetime]::Now
    return $script:dlssOk
}
function Test-DlssFilesNow {
    $d = Get-SlDir
    foreach ($k in $SlFiles.Keys) {
        $f = Join-Path $d $k
        if (-not (Test-Path $f)) { return $false }
        try { if ((Get-FileHash -Path $f -Algorithm SHA256).Hash -ine $SlFiles[$k]) { return $false } } catch { return $false }
    }
    return $true
}
function Update-Dlss-Text { Update-Tech }   # (o painel Tecnologias de imagem cuida dos textos)

# Baixa e instala se faltar. Retorna $true quando os 6 arquivos estao la e conferidos.
function Install-Dlss {
    if (Test-DlssFiles) { return $true }
    if ((-not $script:techConsent) -and ([System.Windows.MessageBox]::Show((T 'dlss_q'), 'RecompZel', 'YesNo', 'Question') -ne 'Yes')) { return $false }
    $tmp = Join-Path $env:TEMP ('recompzel-sl-' + [guid]::NewGuid().ToString('N'))
    $zipObj = $null
    try {
        $txtHelp.Text = T 'dlss_dling'
        $win.Dispatcher.Invoke([action]{}, 'Render')
        New-Item -ItemType Directory -Path $tmp -Force | Out-Null
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        $ProgressPreference = 'SilentlyContinue'
        $zip = Join-Path $tmp 'streamline.zip'
        Invoke-WebRequest -Uri $SlUrl -OutFile $zip -UseBasicParsing
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $zipObj = [System.IO.Compression.ZipFile]::OpenRead($zip)
        $x = Join-Path $tmp 'x'
        New-Item -ItemType Directory -Path $x -Force | Out-Null
        foreach ($k in $SlFiles.Keys) {
            $entry = $zipObj.Entries | Where-Object { $_.FullName -eq ('bin/x64/' + $k) } | Select-Object -First 1
            if ($null -eq $entry) { throw ((T 'dlss_e_pkg') -f $k) }
            $out = Join-Path $x $k
            [System.IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $out, $true)
            if ((Get-FileHash -Path $out -Algorithm SHA256).Hash -ine $SlFiles[$k]) { throw ((T 'dlss_e_hash') -f $k) }
        }
        $lic = $zipObj.Entries | Where-Object { $_.FullName -eq 'bin/x64/nvngx_dlss.license.txt' } | Select-Object -First 1
        if ($null -ne $lic) { [System.IO.Compression.ZipFileExtensions]::ExtractToFile($lic, (Join-Path $x 'NVIDIA-RTX-SDKs-LICENSE.txt'), $true) }
        $srEntry = $zipObj.Entries | Where-Object { $_.FullName -eq ('bin/x64/' + $SlSrName) } | Select-Object -First 1
        if ($null -ne $srEntry) {
            $srOut = Join-Path $x $SlSrName
            [System.IO.Compression.ZipFileExtensions]::ExtractToFile($srEntry, $srOut, $true)
            if ((Get-FileHash -Path $srOut -Algorithm SHA256).Hash -ine $SlSrSha) { Remove-Item $srOut -Force }
        }
        $dest = Get-SlDir
        New-Item -ItemType Directory -Path $dest -Force | Out-Null
        if (Test-Path (Join-Path $x $SlSrName)) { Copy-Item (Join-Path $x $SlSrName) (Join-Path $dest $SlSrName) -Force }
        foreach ($k in $SlFiles.Keys) { Copy-Item (Join-Path $x $k) (Join-Path $dest $k) -Force }
        if (Test-Path (Join-Path $x 'NVIDIA-RTX-SDKs-LICENSE.txt')) { Copy-Item (Join-Path $x 'NVIDIA-RTX-SDKs-LICENSE.txt') $dest -Force }
        Set-Content -Path (Join-Path $dest 'SOURCE.txt') -Value ('Streamline 2.14.16, official NVIDIA package: ' + $SlUrl) -Encoding ASCII
        $script:dlssOkAt = [datetime]::MinValue
        $txtHelp.Text = T 'dlss_done'
        return $true
    } catch {
        [System.Windows.MessageBox]::Show(((T 'dlss_fail') -f $_.Exception.Message), 'RecompZel') | Out-Null
        return $false
    } finally {
        if ($null -ne $zipObj) { $zipObj.Dispose() }
        Remove-Item -Path $tmp -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# hookshot_env.txt vale mais que o ambiente: tira dele o RX_VK_DLSSG de testes manuais, para o launcher mandar
function Clear-DlssEnvFile {
    try {
        $f = Join-Path (Get-OutDir) 'hookshot_env.txt'
        if (Test-Path $f) {
            $lines = @(Get-Content $f)
            $keep = @($lines | Where-Object { $_ -notmatch '^\s*RX_VK_DLSSG\s*=' })
            if ($keep.Count -ne $lines.Count) { Set-Content -Path $f -Value $keep -Encoding ASCII }
        }
    } catch {}
}

# Baixa o componente se faltar. Retorna $true quando ele esta pronto.
function Install-Fsr {
    if (Test-FsrDll) { return $true }
    if ((-not $script:techConsent) -and ([System.Windows.MessageBox]::Show((T 'fsr_q'), 'RecompZel', 'YesNo', 'Question') -ne 'Yes')) { return $false }
    $tmp = Join-Path $env:TEMP ('recompzel-fsr-' + [guid]::NewGuid().ToString('N'))
    try {
        $txtHelp.Text = T 'fsr_dling'
        $win.Dispatcher.Invoke([action]{}, 'Render')
        New-Item -ItemType Directory -Path $tmp -Force | Out-Null
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        $ProgressPreference = 'SilentlyContinue'
        $zip = Join-Path $tmp 'fsr4vk.zip'
        Invoke-WebRequest -Uri $Fsr4vkUrl -OutFile $zip -UseBasicParsing
        Expand-Archive -Path $zip -DestinationPath (Join-Path $tmp 'x') -Force
        $dll = Get-ChildItem -Path (Join-Path $tmp 'x') -Recurse -Filter $Fsr4vkName | Select-Object -First 1
        if ($null -eq $dll) { throw (T 'fsr_e_pkg') }
        if ((Get-FileHash -Path $dll.FullName -Algorithm SHA256).Hash -ine $Fsr4vkSha) { throw (T 'fsr_e_hash') }
        $dest = Get-FsrDir
        New-Item -ItemType Directory -Path $dest -Force | Out-Null
        Copy-Item $dll.FullName (Join-Path $dest $Fsr4vkName) -Force
        foreach ($extra in 'LICENSES', 'SOURCE.txt', 'PATCH.md') {
            $e = Join-Path $dll.DirectoryName $extra
            if (Test-Path $e) { Copy-Item $e $dest -Recurse -Force }
        }
        $txtHelp.Text = T 'fsr_done'
        return $true
    } catch {
        [System.Windows.MessageBox]::Show(((T 'fsr_fail') -f $_.Exception.Message), 'RecompZel') | Out-Null
        return $false
    } finally {
        Remove-Item -Path $tmp -Recurse -Force -ErrorAction SilentlyContinue
    }
}

function Get-Step([double]$p, [string]$cur, [string]$stage) {
    if ($p -ge 100) { return '[OK]' }
    if ($stage -eq $cur) { return '[>>]' }
    return '[  ]'
}

function Format-Min([double]$sec) {
    $m = [int][math]::Ceiling($sec / 60)
    if ($m -lt 1) { return (T 'lt1') }
    if ($m -lt 60) { return "$m min" }
    return ('{0}h{1:00}' -f [int][math]::Floor($m / 60), ($m % 60))
}

# Enquanto o install-tools.ps1 baixa as ferramentas, mostra o progresso dele aqui (ele escreve %LOCALAPPDATA%\RecompZel\tools-status.txt)
function Show-ToolsProgress {
    $f = Join-Path $env:LOCALAPPDATA 'RecompZel\tools-status.txt'
    if (-not (Test-Path -LiteralPath $f)) { return }
    try {
        if (((Get-Date) - (Get-Item -LiteralPath $f).LastWriteTime).TotalMinutes -gt 15) { Remove-Item -LiteralPath $f -Force -ErrorAction SilentlyContinue; return }
        $p = (Get-Content -LiteralPath $f -Raw).Trim().Split('|')
        if ($p.Count -lt 3) { return }
        $pct = [double]$p[0]
        $txtPct.Text = ('{0}%' -f [int][math]::Floor($pct))
        $pbTotal.Value = $pct
        if ($script:lang -eq 'en') { $txtStatus.Text = 'Installing the tools'; $txtNow.Text = $p[2]; $txtNext.Text = 'Then the game build starts by itself.' }
        else { $txtStatus.Text = 'Instalando as ferramentas'; $txtNow.Text = $p[1]; $txtNext.Text = 'Depois o build do jogo comeca sozinho.' }
        $txtStatus.Foreground = '#6FD3A0'
    } catch {}
}

function Update-View {
    $g = $script:g
    $lines = Read-LogLines
    $stage = 'inicio'; $totalFiles = [int]$g.totalFiles; $filesDone = 0
    $planTotal = 0; $prog = -1; $eta = -1; $err = @(); $done = $false; $shEnd = $false
    foreach ($l in $lines) {
        if ($l -match '^@@stage\s+(\S+)') { $stage = $Matches[1]; if ($stage -eq 'shaders') { $shEnd = $false; $prog = -1 } }
        if ($l -match '^(done shaders|the shaders were not prepared now|\[script\] codigo de saida)') { $shEnd = $true }
        if ($l -match 'title 1 .*romfs\s+(\d+)\s+files') { $totalFiles = [int]$Matches[1] }
        if ($l -match '^\s*[\d\.]+\s+MiB written \((\d+) files completed\)') { $filesDone = [int]$Matches[1] }
        if ($l -match '^done:\s+(\d+)\s+files written') { $filesDone = [int]$Matches[1] }
        if ($l -match '^@@plan\s+(\d+)') { $planTotal = [int]$Matches[1] }
        if ($l -match '^@@progress\s+([\d\.]+)') { $prog = [double]$Matches[1] }
        if ($l -match '^@@eta\s+(\d+)') { $eta = [int]$Matches[1] }
        if (($l -match '^(error|fatal)\b') -or ($l -match 'Traceback') -or ($l -match '(?i)Terminou com codigo [1-9]') -or ($l -match '^compiled in .*,\s*[1-9]\d* failed')) { $err += $l }
        if ($l -match '(?i)^@@done|^@@stage\s+done|^the build took|build complete|build finished') { $done = $true }
    }
    $script:lastErrLines = $err
    # a preparacao dos shaders vem depois de "the build took": enquanto roda, ainda nao esta pronto (o log termina com done shaders ou com o aviso de que ficou para o 1o inicio)
    $shRunning = ($stage -eq 'shaders') -and -not $shEnd -and ($err.Count -eq 0)
    if ($shRunning) { $done = $false }

    $later = $stage -notin @('inicio','read','lift','compile')
    $readPct = 0
    if ($stage -eq 'read' -and $totalFiles -gt 0) { $readPct = [math]::Min(100, 100.0 * $filesDone / $totalFiles) }
    elseif ($stage -ne 'inicio') { $readPct = 100 }
    $liftPct = 0; if ($stage -eq 'compile' -or $later) { $liftPct = 100 }

    $compPct = 0
    if ($prog -ge 0) { $compPct = [math]::Min(100, 100.0 * $prog) }
    if ($later) { $compPct = 100 }
    $script:lastCount = [int][math]::Round($compPct / 100.0 * $planTotal)
    $finPct = 0; if ($done) { $finPct = 100 } elseif ($shRunning) { $finPct = 50 + 50 * [math]::Max(0, [math]::Min(1, $prog)) } elseif ($later) { $finPct = 50 }

    $total = ($readPct*$W.read + $liftPct*$W.lift + $compPct*$W.compile + $finPct*$W.finish) / 100.0
    if ($done) { $total = 100 }

    $exe = Find-GameExe
    $ready = ($null -ne $exe) -and (-not $shRunning) -and ($done -or ((($err.Count -eq 0)) -and $later))

    # textos gerais (o texto do jogo vem do games.json em portugues; em ingles usa o da tabela para o Zelda)
    $isZ = ([string]$g.id -eq 'zelda-oot')
    $txtGame.Text = [string]$g.name
    if ($script:lang -eq 'en' -and $isZ) { $txtGameSub.Text = T 'subtitle' } else { $txtGameSub.Text = [string]$g.subtitle }
    $txtPct.Text = ('{0}%' -f [int][math]::Floor($total))
    $pbTotal.Value = $total

    # status, "agora" e "proximo passo" em linguagem simples
    if ($err.Count -gt 0) {
        $txtStatus.Text = T 'st_err'; $txtStatus.Foreground = '#FF7A7A'
        $txtNow.Text = T 'now_err'
        $txtNext.Text = T 'next_err'
    } elseif ($ready) {
        $txtStatus.Text = T 'st_ready'; $txtStatus.Foreground = '#6FD3A0'
        $txtNow.Text = T 'now_ready'
        $txtNext.Text = T 'next_ready'
    } elseif ($shRunning) {
        $txtStatus.Text = T 'st_shaders'; $txtStatus.Foreground = '#6FD3A0'
        $txtNow.Text = T 'now_shaders'
        $txtNext.Text = T 'next_shaders'
    } elseif ($stage -eq 'inicio') {
        $txtStatus.Text = T 'st_none'; $txtStatus.Foreground = '#8FA89C'
        if ($script:lang -eq 'en' -and $isZ) { $txtNow.Text = T 'needs' } else { $txtNow.Text = [string]$g.needs }
        $txtNext.Text = T 'next_none'
    } else {
        $txtStatus.Text = T 'st_build'; $txtStatus.Foreground = '#6FD3A0'
        switch ($stage) {
            'read'    { $txtNow.Text = T 'now_read' }
            'lift'    { $txtNow.Text = T 'now_lift' }
            'compile' { $txtNow.Text = T 'now_compile' }
            default   { $txtNow.Text = T 'now_finish' }
        }
        $txtNext.Text = T 'next_build'
    }

    # tempo: ultima atividade e previsao
    $parts = @()
    $last = $null
    $lp = [string]$g.logPath
    if (Test-Path $lp) { $last = (Get-Item $lp).LastWriteTime }
    if ($script:lastObjTime -and (-not $last -or $script:lastObjTime -gt $last)) { $last = $script:lastObjTime }
    if ($last -and -not $done) {
        $ago = ([datetime]::Now - $last).TotalSeconds
        $parts += ((T 'act_pre') + (Format-Min $ago) + (T 'act_post'))
    }
    if ($stage -eq 'compile' -and $eta -ge 0) {
        $parts += ((T 'eta_pre') + (Format-Min $eta) + (T 'eta_post'))
    }
    if ($script:memText) { $parts += $script:memText }
    $txtTime.Text = ($parts -join '  |  ')

    $txtS1.Text = ((T 's1') -f (Get-Step $readPct 'read' $stage), $readPct)
    $txtS2.Text = ((T 's2') -f (Get-Step $liftPct 'lift' $stage), $liftPct)
    $txtS3.Text = ((T 's3') -f (Get-Step $compPct 'compile' $stage), $compPct, $script:lastCount, $planTotal)
    $txtS4.Text = ((T 's4') -f (Get-Step $finPct 'finish' $stage), $finPct)

    $btnPlay.IsEnabled = $ready
    if ($ready -or $stage -ne 'inicio') { $btnBuild.Content = T 'rebuild' } else { $btnBuild.Content = T 'build' }
}

# ---------- Botoes ----------
$btnFolder.Add_Click({
    $o = Get-OutDir
    if (-not (Test-Path $o)) { New-Item -ItemType Directory -Path $o -Force | Out-Null }
    Start-Process explorer.exe $o
})

$btnBuild.Add_Click({
    $r = [System.Windows.MessageBox]::Show((T 'q_build'), 'RecompZel', 'YesNo', 'Question')
    if ($r -eq 'Yes') {
        $s = [string]$script:g.buildScript
        if (Test-Path $s) {
            Start-GameBuild $s | Out-Null
        } else {
            [System.Windows.MessageBox]::Show(((T 'e_script') -f $s), 'RecompZel') | Out-Null
        }
    }
})

$btnReport.Add_Click({
    $lines = Read-LogLines
    $tail = @($lines | Where-Object { $_ -ne '' } | Select-Object -Last 40)
    $hdr = @('RecompZel relatorio', ('Jogo: ' + [string]$script:g.name), ('Data: ' + (Get-Date -Format 'dd/MM/yyyy HH:mm')), ('Percentual: ' + $txtPct.Text), '--- fim do log ---')
    Set-Clipboard -Value (($hdr + $tail) -join "`r`n")
    $txtHelp.Text = T 'rep_copied'
})

$btnPlay.Add_Click({
    $exe = Find-GameExe
    if ($null -eq $exe) { return }
    $mb = $vramOptions[$cbVram.SelectedIndex].Mb
    if ($mb -gt 0) { [Environment]::SetEnvironmentVariable('RX_VK_VRAM_MB', [string]$mb, 'Process') }
    else { [Environment]::SetEnvironmentVariable('RX_VK_VRAM_MB', $null, 'Process') }
    # com um limite de VRAM de 6 GB ou menos, o espelho de memoria do jogo (3 GB por padrao) tambem encolhe, a um quarto do limite
    if ($mb -gt 0 -and $mb -le 6144) { [Environment]::SetEnvironmentVariable('RX_VK_MIRROR_MB', [string][math]::Min(3072, [int]($mb / 4)), 'Process') }
    else { [Environment]::SetEnvironmentVariable('RX_VK_MIRROR_MB', $null, 'Process') }
    # perfil de memoria: so mexe no que o perfil escolhido define (o limite de VRAM escolhido acima, se houver, vale mais que o do perfil)
    $mp = $memProfiles[[math]::Max(0, $cbMem.SelectedIndex)]
    if ($mp.Vram -gt 0) {
        if ($mb -le 0) { [Environment]::SetEnvironmentVariable('RX_VK_VRAM_MB', [string]$mp.Vram, 'Process') }
        if ($mb -le 0 -or $mb -gt 6144) { [Environment]::SetEnvironmentVariable('RX_VK_MIRROR_MB', [string]$mp.Mirror, 'Process') }
        [Environment]::SetEnvironmentVariable('RX_VK_TARGET_POOL_MB', [string]$mp.Pool, 'Process')
        if ($mp.Tex -gt 0) { [Environment]::SetEnvironmentVariable('RX_VK_TEX_MAX_MB', [string]$mp.Tex, 'Process') } else { [Environment]::SetEnvironmentVariable('RX_VK_TEX_MAX_MB', $null, 'Process') }
    } else {
        [Environment]::SetEnvironmentVariable('RX_VK_TARGET_POOL_MB', $null, 'Process')
        [Environment]::SetEnvironmentVariable('RX_VK_TEX_MAX_MB', $null, 'Process')
    }
    $ms = $uploadOptions[$cbUpload.SelectedIndex].Ms
    if ($ms -ge 0) { [Environment]::SetEnvironmentVariable('RX_VK_UPLOAD_BUDGET_MS', [string]$ms, 'Process') }
    else { [Environment]::SetEnvironmentVariable('RX_VK_UPLOAD_BUDGET_MS', $null, 'Process') }
    # Desligado: RX_VK_FRAMEGEN=0 desliga a interpolacao propria e RX_VK_FSR_FG=0 a do FSR 3.1, valendo mais que o menu do jogo
    $fgSel = $fgOptions[$cbFg.SelectedIndex]
    if ($fgSel.Off) {
        [Environment]::SetEnvironmentVariable('RX_VK_FRAMEGEN', '0', 'Process')
        [Environment]::SetEnvironmentVariable('RX_VK_FSR_FG', '0', 'Process')
    } else {
        [Environment]::SetEnvironmentVariable('RX_VK_FRAMEGEN', $null, 'Process')
        if ($fgSel.Fsr) { [Environment]::SetEnvironmentVariable('RX_VK_FSR_FG', '1', 'Process') }
        else { [Environment]::SetEnvironmentVariable('RX_VK_FSR_FG', $null, 'Process') }
    }
    # economia de RAM: o jogo nao le o arquivo de cache de pipelines (mkw_vk_pipelines.bin, 1 a 3 GB) e nao o grava; o driver usa o cache dele
    if ($chkRam.IsChecked -or $mp.PCache) { [Environment]::SetEnvironmentVariable('RX_VK_PCACHE_LOAD', '0', 'Process') }
    else { [Environment]::SetEnvironmentVariable('RX_VK_PCACHE_LOAD', $null, 'Process') }
    if ($chkDiag.IsChecked) { [Environment]::SetEnvironmentVariable('RX_VK_WATCH_PROG', 'da7a7ab28b8e73d9', 'Process') }
    else { [Environment]::SetEnvironmentVariable('RX_VK_WATCH_PROG', $null, 'Process') }
    # FSR 4: so liga quando o jogo foi construido com ele e o componente esta instalado e conferido
    $useFsr = $false
    [Environment]::SetEnvironmentVariable('RX_VK_FSR4', $null, 'Process')
    [Environment]::SetEnvironmentVariable('RX_VK_FSR_DIR', $null, 'Process')
    $safe = [bool]$chkSafe.IsChecked   # (modo seguro: nada de FSR 4, DLSS nem Streamline)
    if ($chkFsr.IsChecked -and -not $safe) {
        if (-not (Test-FsrBuilt)) {
            if ([System.Windows.MessageBox]::Show((T 'fsr_q_rebuild'), 'RecompZel', 'YesNo', 'Question') -eq 'Yes') {
                $s = [string]$script:g.buildScript
                if (Test-Path $s) {
                    Start-GameBuild $s | Out-Null
                    return
                }
            }
        } elseif (Install-Fsr) {
            $useFsr = $true
            [Environment]::SetEnvironmentVariable('RX_VK_FSR_DIR', (Get-FsrDir), 'Process')
            [Environment]::SetEnvironmentVariable('RX_VK_FSR4', '1', 'Process')
        }
        Update-Fsr-Text
    }
    # DLSS (reescalonamento): so liga quando o jogo foi construido com o SDK da NVIDIA (nvngx_dlss.dll em ngx); senao oferece reconstruir
    $useDsr = $false
    [Environment]::SetEnvironmentVariable('RX_VK_DLSS', $null, 'Process')
    if ($safe -or -not $chkDsr.IsChecked) { Set-DsrChoice $false }
    if ($safe) { Set-FgChoice $false }
    if ($chkDsr.IsChecked -and -not $safe -and (Test-DsrGpu)) {
        if (-not (Test-DsrBuilt)) {
            if ([System.Windows.MessageBox]::Show((T 'dsr_q'), 'RecompZel', 'YesNo', 'Question') -eq 'Yes') {
                $s = [string]$script:g.buildScript
                if (Test-Path $s) {
                    Start-GameBuild $s | Out-Null
                    return
                }
            }
        } else {
            $useDsr = $true
            Set-DsrChoice $true
        }
        Update-Dsr-Text
    }
    # DLSS Frame Generation: so liga com os 6 arquivos da NVIDIA instalados e conferidos
    $useDlss = $false
    Clear-DlssEnvFile
    [Environment]::SetEnvironmentVariable('RX_VK_DLSSG', '0', 'Process')
    if ($chkDlss.IsChecked -and -not $safe -and (Test-DlssGpu)) {
        if (Install-Dlss) {
            $useDlss = $true
            [void](Ensure-SlSr)
            [Environment]::SetEnvironmentVariable('RX_VK_DLSSG', '1', 'Process')
        }
        Update-Dlss-Text
    }
    # a nota da rodada fica sempre em portugues (e lida pelo medir-rodada.ps1)
    $meshNow = Read-Mesh
    $script:roundNote = ('VRAM={0} UPLOAD_BUDGET_MS={1} FRAMEGEN={2} DIAG={3} FSR4={4} MESH={5} DLSSG={6} DLSS={7}' -f $vramOptions[$cbVram.SelectedIndex].Pt, $uploadOptions[$cbUpload.SelectedIndex].Pt, $fgOptions[$cbFg.SelectedIndex].Pt, [bool]$chkDiag.IsChecked, $useFsr, $meshNow, $useDlss, $useDsr)
    $script:gameOut = Get-OutDir
    $script:gameProc = Start-Process -FilePath $exe.FullName -WorkingDirectory $exe.DirectoryName -PassThru
    $txtHelp.Text = T 'started'
})

# ---------- Atualizacao automatica ----------
$timer = New-Object System.Windows.Threading.DispatcherTimer
$timer.Interval = [TimeSpan]::FromSeconds(2)
# ---------- Atualizacao do proprio RecompZel (launcher e codigo do jogo) a partir do GitHub ----------
# O exe leva um numero de build (build.txt, o numero da execucao do CI). A release "launcher" publica o build.txt e o exe mais novos:
# se o numero de la e maior que o desta pasta, o botao Atualizar avisa. Atualizar baixa o exe (hash conferido), atualiza o codigo do jogo
# (so a copia baixada pelo launcher, nunca um clone com git) e abre o exe novo, que troca os scripts e abre o launcher de novo.
$script:updateAvail = $false; $script:updateTask = $null; $script:updateWc = $null
$UpdBase = 'https://github.com/TechHammerBR/RecompZel/releases/download/launcher'
function Get-LocalBuild {
    try { $f = Join-Path $AppDir 'build.txt'; if (Test-Path -LiteralPath $f) { return [int](Get-Content -LiteralPath $f -Raw).Trim() } } catch {}
    return 0
}
function Start-UpdateCheck {
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
        $script:updateWc = New-Object System.Net.WebClient
        $script:updateTask = $script:updateWc.DownloadStringTaskAsync(($UpdBase + '/build.txt?t=' + [guid]::NewGuid().ToString('N')))
    } catch { $script:updateTask = $null }
}
function Poll-UpdateCheck {
    if ($null -eq $script:updateTask -or -not $script:updateTask.IsCompleted) { return }
    $t = $script:updateTask; $script:updateTask = $null
    try {
        if (-not $t.IsFaulted -and -not $t.IsCanceled) {
            $remote = [int]($t.Result.Trim())
            $local = Get-LocalBuild
            if ($local -gt 0 -and $remote -gt $local) { $script:updateAvail = $true; $btnUpdate.Content = T 'upd_avail' }
        }
    } catch {}
    try { $script:updateWc.Dispose() } catch {}
}
function Update-GameSource {
    # so a copia que o launcher baixou (sem .git); quem usa um clone atualiza com git pull ou atualizar-fork.ps1
    $src = Join-Path $env:LOCALAPPDATA 'RecompZel\RecompZel'
    if (-not (Test-Path -LiteralPath (Join-Path $src 'nx2\make_game.py')) -or (Test-Path -LiteralPath (Join-Path $src '.git'))) { return $false }
    $tmp = Join-Path $env:TEMP ('recompzel-upd-' + [guid]::NewGuid().ToString('N'))
    try {
        New-Item -ItemType Directory -Force -Path $tmp | Out-Null
        $zip = Join-Path $tmp 'src.zip'
        Invoke-WebRequest -UseBasicParsing -Uri 'https://github.com/TechHammerBR/RecompZel/archive/refs/heads/main.zip' -OutFile $zip
        Expand-Archive -LiteralPath $zip -DestinationPath $tmp -Force
        $inner = Get-ChildItem $tmp -Directory | Select-Object -First 1
        Copy-Item -Path (Join-Path $inner.FullName '*') -Destination $src -Recurse -Force
        return $true
    } finally { Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue }
}
$btnUpdate.Add_Click({
    if ([System.Windows.MessageBox]::Show($win, (T 'upd_ask'), 'RecompZel', 'YesNo', 'Question') -ne 'Yes') { return }
    $btnUpdate.IsEnabled = $false
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
        $tmp = Join-Path $env:TEMP 'RecompZel-Launcher-novo.exe'
        Invoke-WebRequest -UseBasicParsing -Uri ($UpdBase + '/RecompZel-Launcher.exe') -OutFile $tmp
        $want = ((Invoke-WebRequest -UseBasicParsing -Uri ($UpdBase + '/RecompZel-Launcher.exe.sha256')).Content).Trim().Split(' ')[0]
        if ((Get-FileHash -Path $tmp -Algorithm SHA256).Hash -ine $want) { throw 'arquivo baixado nao confere (hash)' }
        $srcOk = Update-GameSource
        if ($srcOk) { [System.Windows.MessageBox]::Show($win, (T 'upd_src_ok'), 'RecompZel') | Out-Null }
        # abre o exe novo depois que este launcher fechar (ele troca os scripts e abre o launcher de novo)
        $cmd = "Start-Sleep -Seconds 2; Start-Process -FilePath '" + $tmp + "'"
        Start-Process powershell.exe -ArgumentList @('-NoProfile', '-WindowStyle', 'Hidden', '-Command', ('"' + $cmd + '"'))
        $win.Close()
    } catch {
        [System.Windows.MessageBox]::Show($win, ((T 'upd_fail') -f $_.Exception.Message), 'RecompZel') | Out-Null
        $btnUpdate.IsEnabled = $true
    }
})

# Enquanto o jogo roda, mostra a memoria dele (RAM e VRAM, com o pico): serve para ver o que o jogo usa de verdade e comparar as opcoes de economia
$script:memTick = 0; $script:memText = ''; $script:memPeakRam = 0.0; $script:memPeakVram = 0.0
function Sample-GameMem {
    $p = $script:gameProc
    if ($null -eq $p) { $script:memText = ''; return }
    try {
        if ($p.HasExited) { $script:memText = ''; return }
        $script:memTick++
        if ($script:memTick % 3 -ne 1) { return }   # (a cada 6 s: amostrar o contador da GPU custa)
        $p.Refresh()
        $ram = [double]$p.PrivateMemorySize64 / 1GB
        $vram = -1.0
        try {
            $c = Get-Counter -Counter ('\GPU Process Memory(pid_{0}_*)\Dedicated Usage' -f $p.Id) -ErrorAction Stop
            $vram = (($c.CounterSamples | Measure-Object -Property CookedValue -Sum).Sum) / 1GB
        } catch {}
        if ($ram -gt $script:memPeakRam) { $script:memPeakRam = $ram }
        if ($vram -gt $script:memPeakVram) { $script:memPeakVram = $vram }
        $vtxt = if ($vram -ge 0) { ('{0:N1} GB (pico {1:N1})' -f $vram, $script:memPeakVram) } else { '?' }
        $script:memText = ((T 'mem_now') -f ('{0:N1} GB (pico {1:N1})' -f $ram, $script:memPeakRam), $vtxt)
    } catch { $script:memText = '' }
}
function Check-Game {
    Sample-GameMem
    if ($null -eq $script:gameProc) { return }
    try { if (-not $script:gameProc.HasExited) { return } } catch { $script:gameProc = $null; return }
    $script:gameProc = $null
    try {
        $dir = Join-Path $AppDir 'rodadas'
        if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
        $n = @(Get-ChildItem $dir -Filter 'rodada-*.txt' -ErrorAction SilentlyContinue).Count + 2
        $name = ('rodada-{0:00}-{1}' -f $n, (Get-Date -Format 'yyyyMMdd-HHmmss'))
        $src = Join-Path $script:gameOut 'hookshot_log.txt'
        if (Test-Path $src) {
            $hdr = @('### RecompZel, ' + $name, '### ' + $script:roundNote)
            $nota = ([string]$txtNotas.Text).Trim() -replace '\s*[\r\n]+\s*', ' / '
            if ($nota) { $hdr += ('### NOTA: ' + $nota) }
            $hdr += '### ------------------------------'
            $arq = Join-Path $dir ($name + '.txt')
            ($hdr + (Get-Content $src)) | Set-Content $arq -Encoding UTF8
            $txtNotas.Text = ''
            try {
                $res = Join-Path $dir ($name + '-resumo.txt')
                & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'medir-rodada.ps1') -Log $arq -Saida $res | Out-Null
                if (Test-Path $res) { $txtResumo.Tag = 'real'; $txtResumo.Text = ((Get-Content $res | Select-Object -First 12) -join [Environment]::NewLine) }
            } catch {}
            $ini = Join-Path $script:gameOut 'hookshot_options.ini'
            if (Test-Path $ini) { Copy-Item $ini (Join-Path $dir ($name + '.ini')) }
            $txtHelp.Text = ((T 'saved') -f ($dir + '\' + $name + '.txt'))
        }
    } catch {}
    Refresh-Mesh
}
# ---------- Painel "Tecnologias de imagem": a placa detectada, uma etiqueta por tecnologia e a instalacao de uma vez ----------
$script:gpuNames = $null
function Get-GpuNames {
    if ($null -ne $script:gpuNames) { return $script:gpuNames }
    $script:gpuNames = @()
    try {
        $script:gpuNames = @(Get-CimInstance Win32_VideoController -ErrorAction Stop | ForEach-Object { [string]$_.Name } | Where-Object { $_ -and $_ -notmatch 'Basic|Remote|Virtual' })
    } catch {}
    return $script:gpuNames
}
# FSR 4 e da AMD (Radeon): em outras placas fica marcado como experimental e fora do "instalar tudo"
$script:fsrGpu = $null
function Test-FsrGpu {
    if ($null -ne $script:fsrGpu) { return $script:fsrGpu }
    $script:fsrGpu = $false
    foreach ($n in (Get-GpuNames)) { if ($n -match 'AMD|Radeon') { $script:fsrGpu = $true } }
    return $script:fsrGpu
}
$script:brushes = @{}
function Get-Brush([string]$hex) {
    if (-not $script:brushes.ContainsKey($hex)) { $script:brushes[$hex] = (New-Object Windows.Media.BrushConverter).ConvertFromString($hex) }
    return $script:brushes[$hex]
}
function Set-Badge($tb, [string]$key, [string]$hex) {
    $tb.Text = T $key
    $tb.Foreground = Get-Brush $hex
}
$script:fsrOk = $false; $script:fsrOkAt = [datetime]::MinValue
function Test-FsrReady {
    if (([datetime]::Now - $script:fsrOkAt).TotalSeconds -lt 10) { return $script:fsrOk }
    $script:fsrOk = [bool](Test-FsrDll); $script:fsrOkAt = [datetime]::Now
    return $script:fsrOk
}
# Tudo que a placa suporta fica ativo (as caixas ficam escondidas e seguem a placa); o usuario escolhe dentro do jogo. Modo seguro: nada.
function Update-Tech {
    $green = '#6FD3A0'; $amber = '#E3B65B'; $grey = '#8FA89C'; $red = '#D9826B'
    $names = @(Get-GpuNames)
    if ($names.Count -gt 0) { $txtGpu.Text = ((T 'tech_gpu') -f ($names -join ' / ')) } else { $txtGpu.Text = ((T 'tech_gpu') -f (T 'tech_gpu_none')) }
    $safe = [bool]$chkSafe.IsChecked
    $txtSafe.Text = if ($safe) { T 'safe_on' } else { T 'safe_off' }
    $hasDsr = Test-DsrGpu; $hasDlss = Test-DlssGpu; $hasFsr = Test-FsrGpu
    $chkDsr.IsChecked = ((-not $safe) -and $hasDsr)
    $chkDlss.IsChecked = ((-not $safe) -and $hasDlss)
    $chkFsr.IsChecked = ((-not $safe) -and $hasFsr)
    if ($safe) {
        foreach ($b in @($badgeDsr, $badgeDlss, $badgeFsr)) { Set-Badge $b 'badge_safe' $grey }
        foreach ($t in @($txtDsr, $txtDlss, $txtFsr)) { $t.Text = T 'st_safe' }
        return
    }
    if (-not $hasDsr) { Set-Badge $badgeDsr 'badge_no' $red; $txtDsr.Text = T 'dsr_nogpu' }
    elseif (Test-DsrBuilt) { Set-Badge $badgeDsr 'badge_ok' $green; $txtDsr.Text = T 'st_dsr_on' }
    else { Set-Badge $badgeDsr 'badge_todo' $amber; $txtDsr.Text = T 'st_dsr_todo' }
    if (-not $hasDlss) { Set-Badge $badgeDlss 'badge_no' $red; $txtDlss.Text = T 'dlss_nogpu' }
    elseif (Test-DlssFiles) { Set-Badge $badgeDlss 'badge_ok' $green; $txtDlss.Text = T 'st_dlss_on' }
    else { Set-Badge $badgeDlss 'badge_todo' $amber; $txtDlss.Text = T 'st_dlss_todo' }
    if (-not $hasFsr) { Set-Badge $badgeFsr 'badge_off' $grey; $txtFsr.Text = T 'st_fsr_other' }
    elseif (-not (Test-FsrBuilt)) { Set-Badge $badgeFsr 'badge_todo' $amber; $txtFsr.Text = T 'st_fsr_rebuild' }
    elseif (Test-FsrReady) { Set-Badge $badgeFsr 'badge_ok' $green; $txtFsr.Text = T 'st_fsr_on' }
    else { Set-Badge $badgeFsr 'badge_todo' $amber; $txtFsr.Text = T 'st_fsr_todo' }
}
# Um so consentimento para tudo que a placa suporta: marca as caixas, baixa os componentes (Install-Dlss e Install-Fsr nao perguntam de novo)
function Install-AllTech {
    $doDsr = Test-DsrGpu; $doDlss = Test-DlssGpu; $doFsr = Test-FsrGpu
    $names = @()
    if ($doDsr) { $names += 'NVIDIA DLSS' }
    if ($doDlss) { $names += 'NVIDIA DLSS Frame Generation' }
    if ($doFsr) { $names += 'AMD FSR 4' }
    if ($names.Count -eq 0) { [System.Windows.MessageBox]::Show((T 'tech_none'), 'RecompZel') | Out-Null; return }
    if ([System.Windows.MessageBox]::Show(((T 'tech_all_q') -f ($names -join ', ')), 'RecompZel', 'YesNo', 'Question') -ne 'Yes') { return }
    $script:techConsent = $true
    $bad = $false
    try {
        $script:loading = $true
        if ($doDsr) { $chkDsr.IsChecked = $true }
        if ($doDlss) { $chkDlss.IsChecked = $true }
        if ($doFsr) { $chkFsr.IsChecked = $true }
        $chkSafe.IsChecked = $false
        $script:loading = $false
        Save-Settings
        if ($doDsr) { Set-DsrChoice $true }
        if ($doDlss) { Set-FgChoice $true }
        if ($doDlss -and -not (Install-Dlss)) { $bad = $true }
        if ($doFsr -and -not (Install-Fsr)) { $bad = $true }
        if ($doDlss) { [void](Ensure-SlSr) }
    } finally {
        $script:loading = $false
        $script:techConsent = $false
    }
    Update-Tech
    $rebuild = ($doDsr -and -not (Test-DsrBuilt)) -or ($doFsr -and -not (Test-FsrBuilt))
    if ($bad) { $txtHelp.Text = T 'tech_fail' }
    elseif ($rebuild) { $txtHelp.Text = T 'tech_done_rebuild' }
    else { $txtHelp.Text = T 'tech_done' }
}
$btnTechAll.Add_Click({ Install-AllTech })
# O painel de tecnologias muda raramente: atualiza a cada 5 ticks (10 s), e na hora quando o usuario mexe (os botoes chamam Update-Tech)
$script:techTick = 0
$timer.Add_Tick({
    Update-View; Show-ToolsProgress; Check-Game; Poll-UpdateCheck
    $script:techTick++
    if ($script:techTick -ge 5) { $script:techTick = 0; Update-Tech }
})
Start-UpdateCheck
$timer.Start()
Update-View
Update-Tech
Refresh-Mesh
Update-Shortcuts

[void]$win.ShowDialog()

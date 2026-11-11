# launcher.ps1  -  RecompZel Launcher v3 (original, feito para o nosso projeto)
# Uso: powershell -ExecutionPolicy Bypass -File C:\DEV\launcher.ps1
# Le o build.log e a pasta de trabalho. Nao apaga nada. Reconstruir pede confirmacao.
# Idioma: Portugues (Brasil) ou English, no canto superior esquerdo. Perfis de jogos: C:\DEV\games.json.
# A pasta do jogo e C:\Games\RecompZel. Se ainda existir so a antiga (C:\Games\HookshotDev), ela continua sendo usada.

Add-Type -AssemblyName PresentationFramework, PresentationCore, WindowsBase

$ProfilesPath = 'C:\DEV\games.json'
$Cfg          = 'C:\DEV\launcher-settings.json'
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
    git = 'Enviar alteracoes ao GitHub'
    git_tip = 'Copia as ferramentas do projeto para o repositorio e envia tudo ao GitHub. Use depois de qualquer mudanca.'
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
    up_0 = 'Padrao do jogo (40 ms)'
    up_1 = '120 ms'
    up_2 = 'Sem adiamento (0 ms)'
    fg_t = 'Metodo de geracao de quadros'
    fg_0 = 'Hookshot (padrao, 2x a 8x)'
    fg_1 = 'AMD FSR 3.1 (so 2x)'
    fg_2 = 'Desligado (sem geracao de quadros)'
    diag = 'Registrar diagnostico (buffer sem conexao)'
    fsr = 'Usar AMD FSR 4 (mais quadros por segundo)'
    fsr_off = 'Desligado. Se ligar, o launcher cuida do resto.'
    fsr_rebuild = 'O jogo sera reconstruido uma vez, com FSR 4, ao clicar em Jogar.'
    fsr_dl = 'Ao clicar em Jogar, baixa um componente de 14 MB (so na primeira vez).'
    fsr_ready = 'Pronto. O FSR 4 sera usado ao clicar em Jogar.'
    fsr_q = 'O FSR 4 precisa de um componente de terceiros (fsr4vk, licenca GPLv3, cerca de 14 MB).{n}{n}Ele nao e da AMD nem nosso: vem do GitHub (0xCydral/bloodborne_pc) e o launcher confere o arquivo antes de usar.{n}{n}Baixar agora? Se escolher Nao, o jogo abre sem FSR 4.'
    fsr_dling = 'Baixando o componente do FSR 4...'
    fsr_done = 'Componente do FSR 4 instalado.'
    fsr_fail = 'Nao consegui instalar o FSR 4: {0}{n}{n}O jogo abre sem FSR 4.'
    fsr_e_pkg = 'o pacote nao tem o componente esperado'
    fsr_e_hash = 'o arquivo baixado nao confere com o esperado (hash diferente)'
    fsr_q_rebuild = 'Este jogo foi construido sem suporte ao FSR 4. Para usar, ele precisa ser reconstruido uma vez (o que ja esta pronto e reaproveitado, entao demora bem menos que a primeira vez).{n}{n}Reconstruir agora? Se escolher Nao, o jogo abre sem FSR 4.'
    help = 'Passe o mouse sobre um botao para ver o que ele faz.'
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
    rep_copied = 'Relatorio copiado. Cole na conversa com Ctrl+V.'
    started = 'Jogo iniciado. Ao fechar o jogo, o log desta rodada e salvo em C:\DEV\rodadas.'
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
    git = 'Send changes to GitHub'
    git_tip = 'Copies the project tools into the repository and sends everything to GitHub. Use it after any change.'
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
    up_0 = 'Game default (40 ms)'
    up_1 = '120 ms'
    up_2 = 'No deferral (0 ms)'
    fg_t = 'Frame generation method'
    fg_0 = 'Hookshot (default, 2x to 8x)'
    fg_1 = 'AMD FSR 3.1 (2x only)'
    fg_2 = 'Off (no frame generation)'
    diag = 'Log diagnostics (unbound buffer)'
    fsr = 'Use AMD FSR 4 (higher frame rate)'
    fsr_off = 'Off. If you turn it on, the launcher handles the rest.'
    fsr_rebuild = 'The game will be rebuilt once, with FSR 4, when you click Play.'
    fsr_dl = 'When you click Play, it downloads a 14 MB component (first time only).'
    fsr_ready = 'Ready. FSR 4 will be used when you click Play.'
    fsr_q = 'FSR 4 needs a third-party component (fsr4vk, GPLv3 license, about 14 MB).{n}{n}It is neither AMD''s nor ours: it comes from GitHub (0xCydral/bloodborne_pc) and the launcher checks the file before using it.{n}{n}Download now? If you choose No, the game opens without FSR 4.'
    fsr_dling = 'Downloading the FSR 4 component...'
    fsr_done = 'FSR 4 component installed.'
    fsr_fail = 'Could not install FSR 4: {0}{n}{n}The game opens without FSR 4.'
    fsr_e_pkg = 'the package does not contain the expected component'
    fsr_e_hash = 'the downloaded file does not match the expected one (different hash)'
    fsr_q_rebuild = 'This game was built without FSR 4 support. To use it, it must be rebuilt once (what is already done is reused, so it takes much less than the first time).{n}{n}Rebuild now? If you choose No, the game opens without FSR 4.'
    help = 'Hover over a button to see what it does.'
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
    rep_copied = 'Report copied. Paste it into the chat with Ctrl+V.'
    started = 'Game started. When you close it, this round''s log is saved in C:\DEV\rodadas.'
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
            logPath     = 'C:\DEV\build.log'
            workDir     = 'C:\DEV\build-work'
            outDir      = 'C:\Games\RecompZel'
            buildScript = 'C:\DEV\build-game.ps1'
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

    <StackPanel Grid.Column="0">
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
      <Button x:Name="btnGit" Style="{StaticResource Row}"/>
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
          <TextBlock x:Name="txtUpT" Foreground="#E6F2EC" FontSize="13"/>
          <ComboBox x:Name="cbUpload" Margin="0,6,0,8" Height="26"/>
          <TextBlock x:Name="txtFgT" Foreground="#E6F2EC" FontSize="13"/>
          <ComboBox x:Name="cbFg" Margin="0,6,0,8" Height="26"/>
          <CheckBox x:Name="chkDiag" Foreground="#E6F2EC" FontSize="12"/>
          <CheckBox x:Name="chkFsr" Foreground="#E6F2EC" FontSize="12" Margin="0,8,0,0"/>
          <TextBlock x:Name="txtFsr" Foreground="#8FA89C" FontSize="11" TextWrapping="Wrap" Margin="20,2,0,0"/>
        </StackPanel>
      </Border>
    </StackPanel>

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
try { if (Test-Path 'C:\DEV\recompzel.ico') { $win.Icon = [Windows.Media.Imaging.BitmapFrame]::Create([Uri]'C:\DEV\recompzel.ico') } } catch {}
foreach ($n in 'cbLang','btnPlay','btnBuild','btnFolder','btnReport','btnGit','cbVram','cbMesh','cbGame','txtGameSub','txtGame','txtPct','pbTotal','txtStatus','txtTime','txtNow','txtNext','txtS1','txtS2','txtS3','txtS4','txtHelp','vramBox','meshBox','tuneBox','cbUpload','chkDiag','cbFg','txtNotas','txtResumo','chkFsr','txtFsr','txtVramT','txtMeshT','txtMesh','txtUpT','txtFgT','lblNow','lblSteps','lblNext','lblNotes','lblSummary') {
    Set-Variable -Name $n -Value $win.FindName($n)
}
$script:defaultHelp = ''

# ---------- Opcoes (a ordem e o indice salvo em launcher-settings.json: nao reordenar) ----------
$vramOptions = @(
    @{ Key = 'vram_d'; Pt = 'Padrao do jogo (70% da VRAM, ate 6 GB)'; Mb = 0 },
    @{ Key = '';       Pt = '8 GB';  Mb = 8192 },
    @{ Key = '';       Pt = '10 GB'; Mb = 10240 },
    @{ Key = '';       Pt = '12 GB'; Mb = 12288 }
)
# Upload de texturas (RX_VK_UPLOAD_BUDGET_MS): 40 ms e o padrao do jogo; 0 = sem adiamento
$uploadOptions = @(
    @{ Key = 'up_0'; Pt = 'Padrao do jogo (40 ms)'; Ms = -1 },
    @{ Key = 'up_1'; Pt = '120 ms'; Ms = 120 },
    @{ Key = 'up_2'; Pt = 'Sem adiamento (0 ms)'; Ms = 0 }
)
# Metodo de geracao de quadros: o do Hookshot (padrao), o FSR 3.1 (RX_VK_FSR_FG=1, so 2x) ou desligado
$fgOptions = @(
    @{ Key = 'fg_0'; Pt = 'Hookshot (padrao, 2x a 8x)'; Fsr = $false; Off = $false },
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
        $btnGit.Content = T 'git';     $btnGit.Tag = T 'git_tip'
        $btnBuild.Tag = T 'build_tip'
        $txtVramT.Text = T 'vram_t'; $txtMeshT.Text = T 'mesh_t'; $txtUpT.Text = T 'up_t'; $txtFgT.Text = T 'fg_t'
        $chkDiag.Content = T 'diag'; $chkFsr.Content = T 'fsr'
        $lblNow.Text = T 'lbl_now'; $lblSteps.Text = T 'lbl_steps'; $lblNext.Text = T 'lbl_next'
        $lblNotes.Text = T 'lbl_notes'; $lblSummary.Text = T 'lbl_summary'
        if ($txtResumo.Tag -ne 'real') { $txtResumo.Text = T 'summary_ph' }
        Fill-Combo $cbVram (@($vramOptions | ForEach-Object { Opt-Label $_ }))
        Fill-Combo $cbUpload (@($uploadOptions | ForEach-Object { Opt-Label $_ }))
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
        if ($c.diag -eq $true) { $chkDiag.IsChecked = $true }
        if ($c.fsr -eq $true) { $chkFsr.IsChecked = $true }
        if ($c.fgIndex -ge 0 -and $c.fgIndex -lt $fgOptions.Count) { $cbFg.SelectedIndex = [int]$c.fgIndex }
    }
} catch {}
$script:loading = $false
Apply-Language

function Save-Settings {
    if ($script:loading) { return }
    try {
        @{ vramIndex = $cbVram.SelectedIndex; uploadIndex = $cbUpload.SelectedIndex; fgIndex = $cbFg.SelectedIndex; diag = [bool]$chkDiag.IsChecked; fsr = [bool]$chkFsr.IsChecked; lang = $script:lang } |
            ConvertTo-Json | Set-Content $Cfg -Encoding ASCII
    } catch {}
}

# ---------- Mesh shaders: le e grava mesh_shaders= no hookshot_options.ini da pasta do jogo ----------
function Get-IniPath { return (Join-Path (Get-OutDir) 'hookshot_options.ini') }
function Test-GameRunning {
    if ($script:gameProc) { try { if (-not $script:gameProc.HasExited) { return $true } } catch {} }
    return [bool](Get-Process -Name 'RecompZel', 'hookshot' -ErrorAction SilentlyContinue)
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
$cbFg.Add_SelectionChanged({ Save-Settings })
$chkDiag.Add_Click({ Save-Settings })
$chkFsr.Add_Click({ Save-Settings; Update-Fsr-Text })
$cbLang.Add_SelectionChanged({
    if ($script:loading) { return }
    if ($cbLang.SelectedIndex -eq 1) { $script:lang = 'en' } else { $script:lang = 'pt' }
    Apply-Language
    Save-Settings
    Update-View
    Update-Fsr-Text
    Refresh-Mesh
})

# ---------- Ajuda ao passar o mouse ----------
foreach ($b in @($btnPlay, $btnBuild, $btnFolder, $btnReport, $btnGit)) {
    $b.Add_MouseEnter({ param($s, $e) $txtHelp.Text = [string]$s.Tag })
    $b.Add_MouseLeave({ $txtHelp.Text = $script:defaultHelp })
}
$vramBox.Add_MouseEnter({ $txtHelp.Text = T 'vram_tip' })
$vramBox.Add_MouseLeave({ $txtHelp.Text = $script:defaultHelp })
$meshBox.Add_MouseEnter({ $txtHelp.Text = T 'mesh_tip' })
$meshBox.Add_MouseLeave({ $txtHelp.Text = $script:defaultHelp })
$tuneBox.Add_MouseEnter({ $txtHelp.Text = T 'help_tune' })
$tuneBox.Add_MouseLeave({ $txtHelp.Text = $script:defaultHelp })

# ---------- Leitura do log ----------
$script:lastCount = 0
$script:lastCountTime = [datetime]::MinValue
$script:lastObjTime = $null
$script:lastErrLines = @()

function Read-LogLines {
    $p = [string]$script:g.logPath
    if (-not (Test-Path $p)) { return @() }
    try {
        $fs = [System.IO.File]::Open($p, 'Open', 'Read', 'ReadWrite')
        $sr = New-Object System.IO.StreamReader($fs)
        $txt = $sr.ReadToEnd(); $sr.Close(); $fs.Close()
        return $txt -split "`r?`n"
    } catch { return @() }
}

function Find-GameExe {
    $o = Get-OutDir
    if (-not (Test-Path $o)) { return $null }
    $own = Join-Path $o 'RecompZel.exe'
    if (Test-Path -LiteralPath $own) { return Get-Item -LiteralPath $own }
    return Get-ChildItem -Path $o -Filter *.exe -File -ErrorAction SilentlyContinue | Select-Object -First 1
}

# ---------- Atalhos: garante o icone do RecompZel e o exe novo (roda ao abrir o launcher) ----------
function Update-Shortcuts {
    try {
        $ico = 'C:\DEV\recompzel.ico'
        if (-not (Test-Path -LiteralPath $ico)) { return }
        $desk = [Environment]::GetFolderPath('Desktop')
        $sh = New-Object -ComObject WScript.Shell
        $changed = $false
        foreach ($n in 'Zelda OoT (RecompZel).lnk', 'RecompZel Launcher.lnk') {
            $f = Join-Path $desk $n
            if (-not (Test-Path -LiteralPath $f)) { continue }
            $l = $sh.CreateShortcut($f)
            $dirty = $false
            if ($l.IconLocation -ne ($ico + ',0')) { $l.IconLocation = $ico; $dirty = $true }
            if ($n -like 'Zelda*') {
                $exe = Find-GameExe
                if ($exe -and $l.TargetPath -ne $exe.FullName) { $l.TargetPath = $exe.FullName; $l.WorkingDirectory = $exe.DirectoryName; $dirty = $true }
            }
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
    try { return ((Get-FileHash -Path $f -Algorithm SHA256).Hash -ieq $Fsr4vkSha) } catch { return $false }
}

function Update-Fsr-Text {
    if (-not [bool]$chkFsr.IsChecked) { $txtFsr.Text = T 'fsr_off'; return }
    if (-not (Test-FsrBuilt)) { $txtFsr.Text = T 'fsr_rebuild'; return }
    if (-not (Test-FsrDll)) { $txtFsr.Text = T 'fsr_dl'; return }
    $txtFsr.Text = T 'fsr_ready'
}

# Baixa o componente se faltar. Retorna $true quando ele esta pronto.
function Install-Fsr {
    if (Test-FsrDll) { return $true }
    if ([System.Windows.MessageBox]::Show((T 'fsr_q'), 'RecompZel', 'YesNo', 'Question') -ne 'Yes') { return $false }
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

function Update-View {
    $g = $script:g
    $lines = Read-LogLines
    $stage = 'inicio'; $totalFiles = [int]$g.totalFiles; $filesDone = 0
    $planTotal = 0; $prog = -1; $eta = -1; $err = @(); $done = $false
    foreach ($l in $lines) {
        if ($l -match '^@@stage\s+(\S+)') { $stage = $Matches[1] }
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

    $later = $stage -notin @('inicio','read','lift','compile')
    $readPct = 0
    if ($stage -eq 'read' -and $totalFiles -gt 0) { $readPct = [math]::Min(100, 100.0 * $filesDone / $totalFiles) }
    elseif ($stage -ne 'inicio') { $readPct = 100 }
    $liftPct = 0; if ($stage -eq 'compile' -or $later) { $liftPct = 100 }

    $compPct = 0
    if ($prog -ge 0) { $compPct = [math]::Min(100, 100.0 * $prog) }
    if ($later) { $compPct = 100 }
    $script:lastCount = [int][math]::Round($compPct / 100.0 * $planTotal)
    $finPct = 0; if ($done) { $finPct = 100 } elseif ($later) { $finPct = 50 }

    $total = ($readPct*$W.read + $liftPct*$W.lift + $compPct*$W.compile + $finPct*$W.finish) / 100.0
    if ($done) { $total = 100 }

    $exe = Find-GameExe
    $ready = ($null -ne $exe) -and ($done -or ((($err.Count -eq 0)) -and $later))

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
            $script:obs0 = $null; $script:lastCountTime = [datetime]::MinValue
            Start-Process powershell.exe -ArgumentList '-NoExit','-ExecutionPolicy','Bypass','-File',$s
        } else {
            [System.Windows.MessageBox]::Show(((T 'e_script') -f $s), 'RecompZel') | Out-Null
        }
    }
})

$btnGit.Add_Click({
    $s = 'C:\DEV\enviar-github.ps1'
    if (Test-Path $s) { Start-Process powershell.exe -ArgumentList '-NoExit','-ExecutionPolicy','Bypass','-File',$s }
    else { [System.Windows.MessageBox]::Show(((T 'e_script2') -f $s), 'RecompZel') | Out-Null }
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
    if ($chkDiag.IsChecked) { [Environment]::SetEnvironmentVariable('RX_VK_WATCH_PROG', 'da7a7ab28b8e73d9', 'Process') }
    else { [Environment]::SetEnvironmentVariable('RX_VK_WATCH_PROG', $null, 'Process') }
    # FSR 4: so liga quando o jogo foi construido com ele e o componente esta instalado e conferido
    $useFsr = $false
    [Environment]::SetEnvironmentVariable('RX_VK_FSR4', $null, 'Process')
    [Environment]::SetEnvironmentVariable('RX_VK_FSR_DIR', $null, 'Process')
    if ($chkFsr.IsChecked) {
        if (-not (Test-FsrBuilt)) {
            if ([System.Windows.MessageBox]::Show((T 'fsr_q_rebuild'), 'RecompZel', 'YesNo', 'Question') -eq 'Yes') {
                $s = [string]$script:g.buildScript
                if (Test-Path $s) {
                    $script:obs0 = $null; $script:lastCountTime = [datetime]::MinValue
                    Start-Process powershell.exe -ArgumentList '-NoExit','-ExecutionPolicy','Bypass','-File',$s
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
    # a nota da rodada fica sempre em portugues (e lida pelo medir-rodada.ps1)
    $meshNow = Read-Mesh
    $script:roundNote = ('VRAM={0} UPLOAD_BUDGET_MS={1} FRAMEGEN={2} DIAG={3} FSR4={4} MESH={5}' -f $vramOptions[$cbVram.SelectedIndex].Pt, $uploadOptions[$cbUpload.SelectedIndex].Pt, $fgOptions[$cbFg.SelectedIndex].Pt, [bool]$chkDiag.IsChecked, $useFsr, $meshNow)
    $script:gameOut = Get-OutDir
    $script:gameProc = Start-Process -FilePath $exe.FullName -WorkingDirectory $exe.DirectoryName -PassThru
    $txtHelp.Text = T 'started'
})

# ---------- Atualizacao automatica ----------
$timer = New-Object System.Windows.Threading.DispatcherTimer
$timer.Interval = [TimeSpan]::FromSeconds(2)
function Check-Game {
    if ($null -eq $script:gameProc) { return }
    try { if (-not $script:gameProc.HasExited) { return } } catch { $script:gameProc = $null; return }
    $script:gameProc = $null
    try {
        $dir = 'C:\DEV\rodadas'
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
                & powershell.exe -NoProfile -ExecutionPolicy Bypass -File 'C:\DEV\medir-rodada.ps1' -Log $arq -Saida $res | Out-Null
                if (Test-Path $res) { $txtResumo.Tag = 'real'; $txtResumo.Text = ((Get-Content $res | Select-Object -First 12) -join [Environment]::NewLine) }
            } catch {}
            $ini = Join-Path $script:gameOut 'hookshot_options.ini'
            if (Test-Path $ini) { Copy-Item $ini (Join-Path $dir ($name + '.ini')) }
            $txtHelp.Text = ((T 'saved') -f ($dir + '\' + $name + '.txt'))
        }
    } catch {}
    Refresh-Mesh
}
$timer.Add_Tick({ Update-View; Check-Game; Update-Fsr-Text })
$timer.Start()
Update-View
Update-Fsr-Text
Refresh-Mesh
Update-Shortcuts

[void]$win.ShowDialog()

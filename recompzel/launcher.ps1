# launcher.ps1  -  RecompZel Launcher v2 (original, feito para o nosso projeto)
# Uso: powershell -ExecutionPolicy Bypass -File C:\DEV\launcher.ps1
# Le o build.log e a pasta de trabalho. Nao apaga nada. Reconstruir pede confirmacao.
# Perfis de jogos: C:\DEV\games.json (criado automaticamente com o Zelda). Para outro jogo, adicione um item na lista.

Add-Type -AssemblyName PresentationFramework, PresentationCore, WindowsBase

$ProfilesPath = 'C:\DEV\games.json'
$Cfg          = 'C:\DEV\launcher-settings.json'
$W = @{ read = 15; lift = 10; compile = 60; finish = 15 }   # pesos do percentual total

# ---------- Perfis de jogos ----------
if (-not (Test-Path $ProfilesPath)) {
    $default = @{ games = @(
        @{
            id          = 'zelda-oot'
            name        = 'Zelda: Ocarina of Time'
            subtitle    = 'Switch 2, recompilado para PC'
            logPath     = 'C:\DEV\build.log'
            workDir     = 'C:\DEV\build-work'
            outDir      = 'C:\Games\HookshotDev'
            buildScript = 'C:\DEV\build-game.ps1'
            totalFiles  = 186583
            needs       = 'Voce precisa do seu proprio arquivo do jogo (.nup). Nada e baixado da internet.'
        }
    ) }
    $default | ConvertTo-Json -Depth 6 | Set-Content $ProfilesPath -Encoding UTF8
}
$games = @((Get-Content $ProfilesPath -Raw | ConvertFrom-Json).games)
$script:g = $games[0]

$xaml = @'
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        Title="RecompZel" Width="860" Height="860" ResizeMode="CanMinimize"
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
      <TextBlock Text="RecompZel" Foreground="#6FD3A0" FontSize="26" FontWeight="SemiBold"/>
      <TextBlock x:Name="txtGameSub" Foreground="#8FA89C" FontSize="12" Margin="0,0,0,10" TextWrapping="Wrap"/>
      <ComboBox x:Name="cbGame" Height="28" Margin="0,0,0,12"/>
      <Button x:Name="btnPlay" Style="{StaticResource Row}" Content="Jogar" Height="64" FontSize="19"
              Tag="Inicia o jogo. Fica desativado ate o jogo estar pronto."/>
      <Button x:Name="btnBuild" Style="{StaticResource Row}" Content="Construir o jogo"
              Tag="Cria o jogo no seu PC a partir do seu arquivo. Demora de dezenas de minutos a mais de uma hora. Voce pode usar o PC normalmente."/>
      <Button x:Name="btnFolder" Style="{StaticResource Row}" Content="Abrir a pasta do jogo"
              Tag="Abre a pasta onde o jogo foi montado."/>
      <Button x:Name="btnReport" Style="{StaticResource Row}" Content="Copiar relatorio para suporte"
              Tag="Copia o final do registro do build. Cole numa conversa para pedir ajuda."/>
      <Button x:Name="btnGit" Style="{StaticResource Row}" Content="Enviar alteracoes ao GitHub"
              Tag="Copia as ferramentas do projeto para o repositorio e envia tudo ao GitHub. Use depois de qualquer mudanca."/>
      <Border x:Name="vramBox" Background="#1B2A25" BorderBrush="#2E4A40" BorderThickness="1" CornerRadius="3" Padding="16,10">
        <StackPanel>
          <TextBlock Text="Memoria de video para texturas" Foreground="#E6F2EC" FontSize="13"/>
          <ComboBox x:Name="cbVram" Margin="0,6,0,0" Height="26"/>
        </StackPanel>
      </Border>
      <Border x:Name="tuneBox" Background="#1B2A25" BorderBrush="#2E4A40" BorderThickness="1" CornerRadius="3" Padding="16,10" Margin="0,8,0,0">
        <StackPanel>
          <TextBlock Text="Upload de texturas por quadro" Foreground="#E6F2EC" FontSize="13"/>
          <ComboBox x:Name="cbUpload" Margin="0,6,0,8" Height="26"/>
          <TextBlock Text="Metodo de geracao de quadros" Foreground="#E6F2EC" FontSize="13"/>
          <ComboBox x:Name="cbFg" Margin="0,6,0,8" Height="26"/>
          <CheckBox x:Name="chkDiag" Content="Registrar diagnostico (buffer sem conexao)" Foreground="#E6F2EC" FontSize="12"/>
          <CheckBox x:Name="chkFsr" Content="Usar AMD FSR 4 (mais quadros por segundo)" Foreground="#E6F2EC" FontSize="12" Margin="0,8,0,0"/>
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

        <TextBlock Text="O que esta acontecendo agora" Foreground="#8FA89C" FontSize="12"/>
        <TextBlock x:Name="txtNow" Foreground="#E6F2EC" FontSize="14" TextWrapping="Wrap" Margin="0,2,0,14"/>

        <TextBlock Text="Etapas" Foreground="#8FA89C" FontSize="12" Margin="0,0,0,4"/>
        <TextBlock x:Name="txtS1" Foreground="#E6F2EC" FontSize="14" Margin="0,0,0,5"/>
        <TextBlock x:Name="txtS2" Foreground="#E6F2EC" FontSize="14" Margin="0,0,0,5"/>
        <TextBlock x:Name="txtS3" Foreground="#E6F2EC" FontSize="14" Margin="0,0,0,5"/>
        <TextBlock x:Name="txtS4" Foreground="#E6F2EC" FontSize="14" Margin="0,0,0,14"/>

        <TextBlock Text="Proximo passo" Foreground="#8FA89C" FontSize="12"/>
        <TextBlock x:Name="txtNext" Foreground="#E6F2EC" FontSize="14" TextWrapping="Wrap" Margin="0,2,0,14"/>

        <TextBlock Text="O que voce viu na ultima partida (salvo junto com o log)" Foreground="#8FA89C" FontSize="12"/>
        <TextBox x:Name="txtNotas" Height="56" AcceptsReturn="True" TextWrapping="Wrap" Margin="0,4,0,12"
                 Background="#0E1714" Foreground="#E6F2EC" BorderBrush="#2E4A40" CaretBrush="#E6F2EC" FontSize="13"/>

        <TextBlock Text="Resumo da ultima rodada" Foreground="#8FA89C" FontSize="12"/>
        <TextBlock x:Name="txtResumo" Foreground="#E6F2EC" FontSize="12" TextWrapping="Wrap" Margin="0,2,0,12"
                   Text="Aparece aqui quando voce fechar o jogo."/>

        <TextBlock x:Name="txtHelp" Foreground="#6E857A" FontSize="12" TextWrapping="Wrap"/>
      </StackPanel>
    </Border>
  </Grid>
</Window>
'@

$reader = New-Object System.Xml.XmlNodeReader ([xml]$xaml)
$win = [Windows.Markup.XamlReader]::Load($reader)
try { if (Test-Path 'C:\DEV\recompzel.ico') { $win.Icon = [Windows.Media.Imaging.BitmapFrame]::Create([Uri]'C:\DEV\recompzel.ico') } } catch {}
foreach ($n in 'btnPlay','btnBuild','btnFolder','btnReport','btnGit','cbVram','cbGame','txtGameSub','txtGame','txtPct','pbTotal','txtStatus','txtTime','txtNow','txtNext','txtS1','txtS2','txtS3','txtS4','txtHelp','vramBox','tuneBox','cbUpload','chkDiag','cbFg','txtNotas','txtResumo','chkFsr','txtFsr') {
    Set-Variable -Name $n -Value $win.FindName($n)
}
$defaultHelp = 'Passe o mouse sobre um botao para ver o que ele faz.'
$txtHelp.Text = $defaultHelp

# ---------- Seletor de jogo ----------
foreach ($x in $games) { [void]$cbGame.Items.Add([string]$x.name) }
$cbGame.SelectedIndex = 0
if ($games.Count -le 1) { $cbGame.Visibility = 'Collapsed' }
$script:obs0 = $null; $script:obsT0 = $null
$cbGame.Add_SelectionChanged({
    $script:g = $games[$cbGame.SelectedIndex]
    $script:obs0 = $null; $script:obsT0 = $null; $script:lastCountTime = [datetime]::MinValue
    Update-View
})

# ---------- Memoria de video ----------
$vramOptions = @(
    @{ Label = 'Padrao do jogo (70% da VRAM, ate 6 GB)'; Mb = 0 },
    @{ Label = '8 GB';  Mb = 8192 },
    @{ Label = '10 GB'; Mb = 10240 },
    @{ Label = '12 GB'; Mb = 12288 }
)
foreach ($o in $vramOptions) { [void]$cbVram.Items.Add($o.Label) }
$cbVram.SelectedIndex = 0

# Upload de texturas (RX_VK_UPLOAD_BUDGET_MS): 40 ms e o padrao do jogo; 0 = sem adiamento
$uploadOptions = @(
    @{ Label = 'Padrao do jogo (40 ms)'; Ms = -1 },
    @{ Label = '120 ms'; Ms = 120 },
    @{ Label = 'Sem adiamento (0 ms)'; Ms = 0 }
)
foreach ($o in $uploadOptions) { [void]$cbUpload.Items.Add($o.Label) }
$cbUpload.SelectedIndex = 0

# Metodo de geracao de quadros: o do Hookshot (padrao, 2x a 8x ou Auto) ou o FSR 3.1 (RX_VK_FSR_FG=1, so 2x)
$fgOptions = @(
    @{ Label = 'Hookshot (padrao, 2x a 8x)'; Fsr = $false; Off = $false },
    @{ Label = 'AMD FSR 3.1 (so 2x)'; Fsr = $true; Off = $false },
    @{ Label = 'Desligado (sem geracao de quadros)'; Fsr = $false; Off = $true }
)
foreach ($o in $fgOptions) { [void]$cbFg.Items.Add($o.Label) }
$cbFg.SelectedIndex = 0
$script:loading = $true
try {
    if (Test-Path $Cfg) {
        $c = Get-Content $Cfg -Raw | ConvertFrom-Json
        if ($c.vramIndex -ge 0 -and $c.vramIndex -lt $vramOptions.Count) { $cbVram.SelectedIndex = [int]$c.vramIndex }
        if ($c.uploadIndex -ge 0 -and $c.uploadIndex -lt $uploadOptions.Count) { $cbUpload.SelectedIndex = [int]$c.uploadIndex }
        if ($c.diag -eq $true) { $chkDiag.IsChecked = $true }
        if ($c.fsr -eq $true) { $chkFsr.IsChecked = $true }
        if ($c.fgIndex -ge 0 -and $c.fgIndex -lt $fgOptions.Count) { $cbFg.SelectedIndex = [int]$c.fgIndex }
    }
} catch {}
$script:loading = $false

function Save-Settings {
    if ($script:loading) { return }
    try {
        @{ vramIndex = $cbVram.SelectedIndex; uploadIndex = $cbUpload.SelectedIndex; fgIndex = $cbFg.SelectedIndex; diag = [bool]$chkDiag.IsChecked; fsr = [bool]$chkFsr.IsChecked } |
            ConvertTo-Json | Set-Content $Cfg -Encoding ASCII
    } catch {}
}
$cbVram.Add_SelectionChanged({ Save-Settings })
$cbUpload.Add_SelectionChanged({ Save-Settings })
$cbFg.Add_SelectionChanged({ Save-Settings })
$chkDiag.Add_Click({ Save-Settings })
$chkFsr.Add_Click({ Save-Settings; Update-Fsr-Text })

# ---------- Ajuda ao passar o mouse ----------
foreach ($b in @($btnPlay, $btnBuild, $btnFolder, $btnReport, $btnGit)) {
    $b.Add_MouseEnter({ param($s, $e) $txtHelp.Text = [string]$s.Tag })
    $b.Add_MouseLeave({ $txtHelp.Text = $defaultHelp })
}
$vramBox.Add_MouseEnter({ $txtHelp.Text = 'Define RX_VK_VRAM_MB ao iniciar o jogo. Valores maiores ajudam nas texturas embaralhadas, se a placa de video tiver folga.' })
$vramBox.Add_MouseLeave({ $txtHelp.Text = $defaultHelp })
$tuneBox.Add_MouseEnter({ $txtHelp.Text = 'Rodada 2: texturas ASTC novas ficam provisorias quando o carregamento passa do limite por quadro. Teste 120 ms ou Sem adiamento. O diagnostico registra o buffer sem conexao no log.' })
$tuneBox.Add_MouseLeave({ $txtHelp.Text = $defaultHelp })

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
    $o = [string]$script:g.outDir
    if (-not (Test-Path $o)) { return $null }
    $own = Join-Path $o 'RecompZel.exe'
    if (Test-Path -LiteralPath $own) { return Get-Item -LiteralPath $own }
    return Get-ChildItem -Path $o -Filter *.exe -File -ErrorAction SilentlyContinue | Select-Object -First 1
}

# ---------- AMD FSR 4 (opcional) ----------
# O jogo precisa ter sido construido com --fsr (marca .hookshot_fsr na pasta do jogo) e o componente fsr4vk precisa estar
# em <pasta do jogo>\fsr4vk. O componente e de terceiros (GPLv3), baixado uma vez do GitHub, e conferido por hash.
$Fsr4vkUrl  = 'https://github.com/0xCydral/bloodborne_pc/releases/download/windows-v1.7.0-beta.2/fsr4vk-v0.4.3-amdfix.zip'
$Fsr4vkSha  = '60a90b24f6789cd52c467471d5a66a0fa6d04e1b8af41095242f50367904f8b2'
$Fsr4vkName = 'amd_fidelityfx_upscaler_vk.dll'

function Get-FsrDir  { return (Join-Path ([string]$script:g.outDir) 'fsr4vk') }
function Test-FsrBuilt { return (Test-Path (Join-Path ([string]$script:g.outDir) '.hookshot_fsr')) }
function Test-FsrDll {
    $f = Join-Path (Get-FsrDir) $Fsr4vkName
    if (-not (Test-Path $f)) { return $false }
    try { return ((Get-FileHash -Path $f -Algorithm SHA256).Hash -ieq $Fsr4vkSha) } catch { return $false }
}

function Update-Fsr-Text {
    if (-not [bool]$chkFsr.IsChecked) { $txtFsr.Text = 'Desligado. Se ligar, o launcher cuida do resto.'; return }
    if (-not (Test-FsrBuilt)) { $txtFsr.Text = 'O jogo sera reconstruido uma vez, com FSR 4, ao clicar em Jogar.'; return }
    if (-not (Test-FsrDll)) { $txtFsr.Text = 'Ao clicar em Jogar, baixa um componente de 14 MB (so na primeira vez).'; return }
    $txtFsr.Text = 'Pronto. O FSR 4 sera usado ao clicar em Jogar.'
}

# Baixa o componente se faltar. Retorna $true quando ele esta pronto.
function Install-Fsr {
    if (Test-FsrDll) { return $true }
    $q = 'O FSR 4 precisa de um componente de terceiros (fsr4vk, licenca GPLv3, cerca de 14 MB).' + "`n`n" +
         'Ele nao e da AMD nem nosso: vem do GitHub (0xCydral/bloodborne_pc) e o launcher confere o arquivo antes de usar.' + "`n`n" +
         'Baixar agora? Se escolher Nao, o jogo abre sem FSR 4.'
    if ([System.Windows.MessageBox]::Show($q, 'RecompZel', 'YesNo', 'Question') -ne 'Yes') { return $false }
    $tmp = Join-Path $env:TEMP ('recompzel-fsr-' + [guid]::NewGuid().ToString('N'))
    try {
        $txtHelp.Text = 'Baixando o componente do FSR 4...'
        $win.Dispatcher.Invoke([action]{}, 'Render')
        New-Item -ItemType Directory -Path $tmp -Force | Out-Null
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        $ProgressPreference = 'SilentlyContinue'
        $zip = Join-Path $tmp 'fsr4vk.zip'
        Invoke-WebRequest -Uri $Fsr4vkUrl -OutFile $zip -UseBasicParsing
        Expand-Archive -Path $zip -DestinationPath (Join-Path $tmp 'x') -Force
        $dll = Get-ChildItem -Path (Join-Path $tmp 'x') -Recurse -Filter $Fsr4vkName | Select-Object -First 1
        if ($null -eq $dll) { throw 'o pacote nao tem o componente esperado' }
        if ((Get-FileHash -Path $dll.FullName -Algorithm SHA256).Hash -ine $Fsr4vkSha) { throw 'o arquivo baixado nao confere com o esperado (hash diferente)' }
        $dest = Get-FsrDir
        New-Item -ItemType Directory -Path $dest -Force | Out-Null
        Copy-Item $dll.FullName (Join-Path $dest $Fsr4vkName) -Force
        foreach ($extra in 'LICENSES', 'SOURCE.txt', 'PATCH.md') {
            $e = Join-Path $dll.DirectoryName $extra
            if (Test-Path $e) { Copy-Item $e $dest -Recurse -Force }
        }
        $txtHelp.Text = 'Componente do FSR 4 instalado.'
        return $true
    } catch {
        [System.Windows.MessageBox]::Show(('Nao consegui instalar o FSR 4: ' + $_.Exception.Message + "`n`nO jogo abre sem FSR 4."), 'RecompZel') | Out-Null
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
    if ($m -lt 1) { return 'menos de 1 minuto' }
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

    # textos gerais
    $txtGame.Text = [string]$g.name
    $txtGameSub.Text = [string]$g.subtitle
    $txtPct.Text = ('{0}%' -f [int][math]::Floor($total))
    $pbTotal.Value = $total

    # status, "agora" e "proximo passo" em linguagem simples
    if ($err.Count -gt 0) {
        $txtStatus.Text = 'Algo deu errado'; $txtStatus.Foreground = '#FF7A7A'
        $txtNow.Text = 'O build encontrou um erro e pode ter parado.'
        $txtNext.Text = 'Clique em "Copiar relatorio para suporte" e cole na conversa para receber ajuda.'
    } elseif ($ready) {
        $txtStatus.Text = 'Pronto para jogar'; $txtStatus.Foreground = '#6FD3A0'
        $txtNow.Text = 'O jogo foi construido e esta instalado no seu PC.'
        $txtNext.Text = 'Clique em Jogar.'
    } elseif ($stage -eq 'inicio') {
        $txtStatus.Text = 'Ainda nao comecou'; $txtStatus.Foreground = '#8FA89C'
        $txtNow.Text = [string]$g.needs
        $txtNext.Text = 'Clique em "Construir o jogo".'
    } else {
        $txtStatus.Text = 'Construindo o jogo'; $txtStatus.Foreground = '#6FD3A0'
        switch ($stage) {
            'read'    { $txtNow.Text = 'Copiando os arquivos do seu jogo para o PC. Isso so usa o disco.' }
            'lift'    { $txtNow.Text = 'Convertendo o codigo do Switch 2 para codigo de PC. E uma etapa rapida.' }
            'compile' { $txtNow.Text = 'Transformando esse codigo em programa. E a etapa mais longa e deixa o processador bem ocupado.' }
            default   { $txtNow.Text = 'Finalizando: juntando as pecas e preparando os efeitos graficos.' }
        }
        $txtNext.Text = 'Nao precisa fazer nada. Pode deixar esta janela aberta e usar o PC normalmente.'
    }

    # tempo: ultima atividade e previsao
    $parts = @()
    $last = $null
    $lp = [string]$g.logPath
    if (Test-Path $lp) { $last = (Get-Item $lp).LastWriteTime }
    if ($script:lastObjTime -and (-not $last -or $script:lastObjTime -gt $last)) { $last = $script:lastObjTime }
    if ($last -and -not $done) {
        $ago = ([datetime]::Now - $last).TotalSeconds
        $parts += ('Ultima atividade ha ' + (Format-Min $ago))
    }
    if ($stage -eq 'compile' -and $eta -ge 0) {
        $parts += ('Faltam cerca de ' + (Format-Min $eta))
    }
    $txtTime.Text = ($parts -join '  |  ')

    $txtS1.Text = ('{0} 1. Ler o jogo ({1:N0}%)' -f (Get-Step $readPct 'read' $stage), $readPct)
    $txtS2.Text = ('{0} 2. Traduzir para PC ({1:N0}%)' -f (Get-Step $liftPct 'lift' $stage), $liftPct)
    $txtS3.Text = ('{0} 3. Montar o programa ({1:N0}%, {2} de {3} pecas)' -f (Get-Step $compPct 'compile' $stage), $compPct, $script:lastCount, $planTotal)
    $txtS4.Text = ('{0} 4. Finalizar e empacotar ({1:N0}%)' -f (Get-Step $finPct 'finish' $stage), $finPct)

    $btnPlay.IsEnabled = $ready
    if ($ready -or $stage -ne 'inicio') { $btnBuild.Content = 'Reconstruir o jogo' } else { $btnBuild.Content = 'Construir o jogo' }
}

# ---------- Botoes ----------
$btnFolder.Add_Click({
    $o = [string]$script:g.outDir
    if (-not (Test-Path $o)) { New-Item -ItemType Directory -Path $o -Force | Out-Null }
    Start-Process explorer.exe $o
})

$btnBuild.Add_Click({
    $r = [System.Windows.MessageBox]::Show('Iniciar o build do jogo? Pode levar mais de uma hora e usa bastante o processador.', 'RecompZel', 'YesNo', 'Question')
    if ($r -eq 'Yes') {
        $s = [string]$script:g.buildScript
        if (Test-Path $s) {
            $script:obs0 = $null; $script:lastCountTime = [datetime]::MinValue
            Start-Process powershell.exe -ArgumentList '-NoExit','-ExecutionPolicy','Bypass','-File',$s
        } else {
            [System.Windows.MessageBox]::Show("Nao achei o script de build: $s", 'RecompZel') | Out-Null
        }
    }
})

$btnGit.Add_Click({
    $s = 'C:\DEV\enviar-github.ps1'
    if (Test-Path $s) { Start-Process powershell.exe -ArgumentList '-NoExit','-ExecutionPolicy','Bypass','-File',$s }
    else { [System.Windows.MessageBox]::Show("Nao achei o script: $s", 'RecompZel') | Out-Null }
})

$btnReport.Add_Click({
    $lines = Read-LogLines
    $tail = @($lines | Where-Object { $_ -ne '' } | Select-Object -Last 40)
    $hdr = @('RecompZel relatorio', ('Jogo: ' + [string]$script:g.name), ('Data: ' + (Get-Date -Format 'dd/MM/yyyy HH:mm')), ('Percentual: ' + $txtPct.Text), '--- fim do log ---')
    Set-Clipboard -Value (($hdr + $tail) -join "`r`n")
    $txtHelp.Text = 'Relatorio copiado. Cole na conversa com Ctrl+V.'
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
            $q = 'Este jogo foi construido sem suporte ao FSR 4. Para usar, ele precisa ser reconstruido uma vez (o que ja esta pronto e reaproveitado, entao demora bem menos que a primeira vez).' + "`n`n" + 'Reconstruir agora? Se escolher Nao, o jogo abre sem FSR 4.'
            if ([System.Windows.MessageBox]::Show($q, 'RecompZel', 'YesNo', 'Question') -eq 'Yes') {
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
    $script:roundNote = ('VRAM={0} UPLOAD_BUDGET_MS={1} FRAMEGEN={2} DIAG={3} FSR4={4}' -f $vramOptions[$cbVram.SelectedIndex].Label, $uploadOptions[$cbUpload.SelectedIndex].Label, $fgOptions[$cbFg.SelectedIndex].Label, [bool]$chkDiag.IsChecked, $useFsr)
    $script:gameOut = [string]$script:g.outDir
    $script:gameProc = Start-Process -FilePath $exe.FullName -WorkingDirectory $exe.DirectoryName -PassThru
    $txtHelp.Text = 'Jogo iniciado. Ao fechar o jogo, o log desta rodada e salvo em C:\DEV\rodadas.'
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
                if (Test-Path $res) { $txtResumo.Text = ((Get-Content $res | Select-Object -First 12) -join [Environment]::NewLine) }
            } catch {}
            $ini = Join-Path $script:gameOut 'hookshot_options.ini'
            if (Test-Path $ini) { Copy-Item $ini (Join-Path $dir ($name + '.ini')) }
            $txtHelp.Text = ('Rodada salva: ' + $dir + '\' + $name + '.txt')
        }
    } catch {}
}
$timer.Add_Tick({ Update-View; Check-Game; Update-Fsr-Text })
$timer.Start()
Update-View
Update-Fsr-Text

[void]$win.ShowDialog()

# Prepara o ambiente de build usando as ferramentas que o HookshotBuilder ja instalou.
# Nao e para rodar sozinho: os outros scripts chamam este com ". $PSScriptRoot\env-recompzel.ps1"
# Repo = a pasta do repositorio. Se este script esta em <repo>\recompzel, usa <repo>; senao (copia em C:\DEV) usa C:\DEV\RecompZel.
# O codigo-fonte: <repo>\recompzel\ (clone ou ZIP); senao C:\DEV\RecompZel (layout antigo) ou %LOCALAPPDATA%\RecompZel\RecompZel;
# se nao existe em lugar nenhum (quem usa so o RecompZel-Launcher.exe), baixa o codigo do GitHub (so o projeto, sem dados do jogo).
# (-eq do PowerShell ignora maiusculas: %LOCALAPPDATA%\RecompZel tambem se chama 'RecompZel'; por isso so vale como clone se o pai tem nx2\make_game.py)
$Repo = if ((Split-Path $PSScriptRoot -Leaf) -eq 'recompzel' -and (Test-Path (Join-Path (Split-Path $PSScriptRoot -Parent) 'nx2\make_game.py'))) { Split-Path $PSScriptRoot -Parent }
        elseif (Test-Path 'C:\DEV\RecompZel\nx2\make_game.py') { 'C:\DEV\RecompZel' }   # (o codigo fundido, no D)
        elseif (Test-Path 'C:\DEV\RecompZel\nx2\make_game.py') { 'C:\DEV\RecompZel' }
        else { Join-Path $env:LOCALAPPDATA 'RecompZel\RecompZel' }
if (-not (Test-Path (Join-Path $Repo 'nx2\make_game.py'))) {
    Write-Host "Baixando o codigo do RecompZel do GitHub (uma vez) para $Repo ..."
    $tmp = Join-Path $env:TEMP ('recompzel-src-' + [guid]::NewGuid().ToString('N'))
    try {
        New-Item -ItemType Directory -Force -Path $tmp | Out-Null
        $zip = Join-Path $tmp 'src.zip'
        [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -UseBasicParsing -Uri 'https://github.com/TechHammerBR/RecompZel/archive/refs/heads/main.zip' -OutFile $zip
        Expand-Archive -LiteralPath $zip -DestinationPath $tmp -Force
        $inner = Get-ChildItem $tmp -Directory | Select-Object -First 1
        New-Item -ItemType Directory -Force -Path (Split-Path $Repo -Parent) | Out-Null
        # nunca apaga a pasta: so copia por cima (o destino e sempre uma pasta so do RecompZel)
        New-Item -ItemType Directory -Force -Path $Repo | Out-Null
        Copy-Item -Path (Join-Path $inner.FullName '*') -Destination $Repo -Recurse -Force
    } catch {
        throw "Nao consegui baixar o codigo do RecompZel (https://github.com/TechHammerBR/RecompZel). Baixe o ZIP do repositorio, extraia e rode o INSTALAR-RECOMPZEL.bat. Detalhe: $($_.Exception.Message)"
    } finally { Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue }
}
function Get-ToolsVersion {
    # a pasta do RecompZel primeiro; senao a que o Builder antigo (HookshotBuilder) instalou
    foreach ($root in @("$env:LOCALAPPDATA\RecompZel\tools", "$env:LOCALAPPDATA\HookshotBuilder\versions")) {
        $v = Get-ChildItem $root -Directory -ErrorAction SilentlyContinue |
             Where-Object { $_.Name -notlike '*.part' -and (Test-Path (Join-Path $_.FullName 'HookshotBuilder\tools\python\python.exe')) } |
             Sort-Object LastWriteTime -Descending | Select-Object -First 1
        if ($v) { return $v }
    }
}
$ver = Get-ToolsVersion
if (-not $ver) {
    # sem ferramentas: instala agora (baixa da release do RecompZel, sem precisar do Builder)
    & (Join-Path $PSScriptRoot 'install-tools.ps1')
    $ver = Get-ToolsVersion
}
if (-not $ver) { throw "As ferramentas de compilacao nao foram instaladas ($env:LOCALAPPDATA\RecompZel\tools)." }
$Tools = Join-Path $ver.FullName 'HookshotBuilder\tools'
$Py = Join-Path $Tools 'python\python.exe'
if (-not (Test-Path -LiteralPath $Py)) { throw "Python do Builder nao encontrado: $Py" }

$env:PYTHONIOENCODING = 'utf-8'
$env:RX_CPM = Join-Path $Tools 'cpm'
$env:WGPU_NATIVE = Join-Path $Tools 'wgpu-native'
if (Test-Path (Join-Path $Tools 'emsdk')) { $env:EMSDK = Join-Path $Tools 'emsdk' }

$mingw = Join-Path $Tools 'llvm-mingw'
if (-not (Test-Path (Join-Path $mingw 'bin\clang.exe'))) {
  $sub = Get-ChildItem $mingw -Directory -ErrorAction SilentlyContinue |
         Where-Object { Test-Path (Join-Path $_.FullName 'bin\clang.exe') } | Select-Object -First 1
  if ($sub) { $mingw = $sub.FullName }
}
$env:HOOKSHOT_MINGW = $mingw

# Pecas pre-compiladas que um clone nao traz: copia .dll .exe .lib .sha1 de tools\third_party
$srcTp = Join-Path $Tools 'third_party'
if (Test-Path $srcTp) {
  Get-ChildItem $srcTp -Recurse -File | Where-Object { $_.Extension -in '.dll', '.exe', '.lib', '.sha1' } | ForEach-Object {
    $rel = $_.FullName.Substring($srcTp.Length).TrimStart('\')
    $dst = Join-Path (Join-Path $Repo 'third_party') $rel
    New-Item -ItemType Directory -Force -Path (Split-Path $dst) | Out-Null
    Copy-Item -LiteralPath $_.FullName -Destination $dst -Force
  }
}
# Lista de funcoes quentes, ordem de link, perfil e icone: tools\work -> work\
$srcWork = Join-Path $Tools 'work'
if (Test-Path $srcWork) {
  robocopy $srcWork (Join-Path $Repo 'work') /E /NFL /NDL /NJH /NJS /NP | Out-Null
}

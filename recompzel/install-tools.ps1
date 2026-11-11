# install-tools.ps1 - instala as ferramentas de compilacao do RecompZel (Python, compilador, pacotes), uma vez, sem o Builder.
# Le a lista hookshot-setup.txt da release "nightly" do repositorio, baixa cada parte, confere o SHA-256 e extrai com o tar.exe do Windows
# em %LOCALAPPDATA%\RecompZel\tools\<versao> (a pasta que o env-recompzel.ps1 procura primeiro; a do Builder antigo, HookshotBuilder\versions, tambem serve). Pula so o programa grafico do Builder (.NET).
# Chamado pelo env-recompzel.ps1 quando as ferramentas nao existem; pode rodar sozinho.
param([string]$ListUrl = 'https://github.com/TechHammerBR/RecompZel/releases/download/nightly/hookshot-setup.txt')
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'   # (sem a barra do PowerShell: o download fica muito mais rapido)
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12

$base = Join-Path $env:LOCALAPPDATA 'RecompZel'
$versions = Join-Path $base 'tools'
$downloads = Join-Path $base 'downloads'

function Get-WithRetry([string]$url, [string]$outFile) {
    for ($i = 1; $i -le 4; $i++) {
        try { Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $outFile; return }
        catch { if ($i -eq 4) { throw }; Write-Host ('O GitHub nao respondeu. Tentando de novo em ' + (3 * $i) + ' s...'); Start-Sleep -Seconds (3 * $i) }
    }
}

Write-Host 'Instalando as ferramentas de compilacao do RecompZel (so uma vez, uns 400 MB)...'
try { $raw = (Invoke-WebRequest -UseBasicParsing -Uri $ListUrl).Content }
catch { throw ('Nao consegui ler a lista de ferramentas em ' + $ListUrl + '. Verifique a internet e tente de novo. Detalhe: ' + $_.Exception.Message) }
if ($raw -is [byte[]]) { $raw = [Text.Encoding]::UTF8.GetString($raw) }

# linhas: tag <versao>  |  part <sha256> <bytes> <pasta> <pasta no zip ou -> <novo nome ou -> <url>
$tag = $null
$parts = @()
foreach ($line in ($raw -split "`n")) {
    $w = $line.Trim() -split '\s+'
    if ($w.Count -ge 2 -and $w[0] -eq 'tag') { $tag = $w[1] }
    elseif ($w.Count -eq 7 -and $w[0] -eq 'part') {
        $parts += [pscustomobject]@{ Sha = $w[1]; Size = [int64]$w[2]; Dest = $w[3]; From = $w[4]; To = $w[5]; Url = $w[6] }
    }
}
if (-not $tag -or $parts.Count -eq 0) { throw 'A lista de ferramentas veio vazia ou num formato inesperado.' }
$parts = @($parts | Where-Object { $_.Url -notmatch 'HookshotBuilder-dotnet-' })   # (o .NET so serve ao Builder grafico)

$final = Join-Path $versions $tag
$work = $final + '.part'
New-Item -ItemType Directory -Force -Path $versions, $downloads | Out-Null
if (Test-Path -LiteralPath $work) { Remove-Item -LiteralPath $work -Recurse -Force }
if (Test-Path -LiteralPath $final) { Remove-Item -LiteralPath $final -Recurse -Force }
New-Item -ItemType Directory -Force -Path $work | Out-Null

$n = 0
foreach ($p in $parts) {
    $n++
    $zip = Join-Path $downloads ($p.Sha + '.zip')
    $ok = (Test-Path -LiteralPath $zip) -and ((Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash -ieq $p.Sha)
    if (-not $ok) {
        Write-Host ('Baixando parte {0} de {1} ({2} MB)...' -f $n, $parts.Count, [math]::Round($p.Size / 1MB))
        $tmp = $zip + '.part'
        Get-WithRetry $p.Url $tmp
        if ((Get-FileHash -LiteralPath $tmp -Algorithm SHA256).Hash -ine $p.Sha) {
            Remove-Item -LiteralPath $tmp -Force
            throw ('A parte ' + $n + ' baixou errada (o hash nao confere). Tente de novo.')
        }
        Move-Item -LiteralPath $tmp -Destination $zip -Force
    }
    Write-Host ('Extraindo parte {0} de {1}...' -f $n, $parts.Count)
    $dest = if ($p.Dest -eq '.') { $work } else { Join-Path $work ($p.Dest -replace '/', '\') }
    New-Item -ItemType Directory -Force -Path $dest | Out-Null
    & (Join-Path $env:WINDIR 'System32\tar.exe') -xf $zip -C $dest
    if ($LASTEXITCODE -ne 0) { throw ('O tar.exe do Windows falhou na parte ' + $n + ' (codigo ' + $LASTEXITCODE + ').') }
    if ($p.From -ne '-' -and $p.To -ne '-') {
        $from = Join-Path $dest $p.From
        $to = Join-Path $dest $p.To
        if (-not (Test-Path -LiteralPath $to)) { Move-Item -LiteralPath $from -Destination $to }
    }
}

$py = Join-Path $work 'HookshotBuilder\tools\python\python.exe'
if (-not (Test-Path -LiteralPath $py)) {
    throw ('O Python nao apareceu depois de extrair (o antivirus pode ter removido). Libere a pasta ' + $base + ' no antivirus e tente de novo.')
}
Move-Item -LiteralPath $work -Destination $final
Set-Content -LiteralPath (Join-Path $final 'installed.txt') -Value $tag
Remove-Item -LiteralPath $downloads -Recurse -Force -ErrorAction SilentlyContinue
Write-Host 'Ferramentas instaladas.' -ForegroundColor Green

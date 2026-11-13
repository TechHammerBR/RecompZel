# achar-shader.ps1 - acha, ao vivo, qual shader do jogo causa o flicker de cor (cena azulada por um quadro).
# Busca por metades: o jogo esconde metade dos objetos da cena por vez (RX_VK_SKIP_FILE, relido a cada 300 ms) e voce
# so responde se ainda pisca. Com ~200 shaders na cena sao ~8 rodadas de 1 minuto.
# Uso: coloque esta pasta dentro da pasta do jogo (onde esta o RecompZel.exe) e rode "Abrir com diagnostico.bat".
# Nao apaga nada: o pular-shaders.txt original volta como estava no fim (ou se voce fechar a janela, rode de novo e
# escolha restaurar).
param([string]$GameDir = '')

$ErrorActionPreference = 'Stop'
if (-not $GameDir) { $GameDir = Split-Path $PSScriptRoot -Parent }
if (-not (Test-Path (Join-Path $GameDir 'RecompZel.exe'))) {
    if (Test-Path (Join-Path $PSScriptRoot 'RecompZel.exe')) { $GameDir = $PSScriptRoot }
    else {
        Write-Host 'Nao achei o RecompZel.exe. Coloque a pasta achar-flicker DENTRO da pasta do jogo.' -ForegroundColor Red
        Read-Host 'ENTER para sair'; exit 1
    }
}
$diag = Join-Path $GameDir 'diag'
$skip = Join-Path $GameDir 'pular-shaders.txt'
$bak = Join-Path $diag 'pular-shaders.original.txt'
$log = Join-Path $diag 'bissecao.txt'
New-Item -ItemType Directory -Force -Path $diag | Out-Null

function Say($t, $c = 'White') { Write-Host $t -ForegroundColor $c }
function Note($t) { Add-Content -Path $log -Value ("[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $t) }
function Ask($q, $opts) {
    while ($true) {
        $a = (Read-Host $q).Trim().ToLower()
        if ($opts -contains $a) { return $a }
        Say ("Responda com: " + ($opts -join ' / ')) 'Yellow'
    }
}

# o que ja estava no pular-shaders.txt (o brilho da sala das teias, por exemplo) fica sempre escondido
$base = @()
if (Test-Path $bak) {
    if ((Ask 'Achei um backup de uma busca anterior. Restaurar o pular-shaders.txt original e sair? (s/n)' @('s','n')) -eq 's') {
        Copy-Item $bak $skip -Force; Remove-Item $bak; Say 'Restaurado.' 'Green'; Read-Host 'ENTER para sair'; exit 0
    }
} elseif (Test-Path $skip) { Copy-Item $skip $bak -Force }
if (Test-Path $bak) { $base = @(Get-Content $bak | Where-Object { $_ -match '^[0-9a-fA-F]{16}' }) }
function Write-Skip($keys) { [IO.File]::WriteAllText($skip, ((@($base) + @($keys)) -join "`n") + "`n") }
Write-Skip @()
Note "inicio; pasta do jogo $GameDir; ja escondidos: $($base -join ',')"

# abre o jogo com o diagnostico (o launcher, se achar, para manter as suas opcoes de DLSS e geracao de quadros)
$env:RX_VK_DRAW_STATS = $diag
$env:RX_VK_SKIP_FILE = $skip
$launcher = $null
foreach ($p in @((Join-Path $GameDir 'RecompZel Launcher.exe'), (Join-Path $env:LOCALAPPDATA 'RecompZel\RecompZel Launcher.exe'))) {
    if (Test-Path $p) { $launcher = $p; break }
}
if (-not $launcher) {
    $lnk = Join-Path ([Environment]::GetFolderPath('Desktop')) 'RecompZel Launcher.lnk'
    if (Test-Path $lnk) { $launcher = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk).TargetPath }
}
if (Get-Process RecompZel -ErrorAction SilentlyContinue) {
    Say 'O jogo ja esta aberto. FECHE o jogo e rode de novo (ele precisa abrir por aqui para o diagnostico valer).' 'Red'
    Read-Host 'ENTER para sair'; exit 1
}
if ($launcher) { Say "Abrindo o launcher: $launcher"; Start-Process -FilePath $launcher -WorkingDirectory (Split-Path $launcher) }
else { Say 'Launcher nao achado: abrindo o jogo direto.'; Start-Process -FilePath (Join-Path $GameDir 'RecompZel.exe') -WorkingDirectory $GameDir }
Note "aberto por: $(if ($launcher) { $launcher } else { 'RecompZel.exe' })"

Say ''
Say '1) Clique em Jogar (se abriu o launcher) e va ate o lugar onde a cena PISCA AZULADA.' 'Cyan'
Say '   Use as mesmas opcoes de sempre (com DLSS/DLAA e geracao de quadros pisca mais: mais facil de ver).' 'Cyan'
Read-Host '2) Quando estiver la, com a cena piscando, volte aqui e aperte ENTER'

# a lista dos shaders desenhados naquele quadro
$t0 = Get-Date
New-Item -ItemType File -Force -Path (Join-Path $diag 'draw_stats.now') | Out-Null
Say 'Lendo os shaders da cena (volte para a janela do jogo por uns segundos)...'
$stats = $null
for ($i = 0; $i -lt 60 -and -not $stats; $i++) {
    Start-Sleep -Milliseconds 500
    $stats = Get-ChildItem $diag -Filter 'draw_stats_*.txt' | Where-Object { $_.LastWriteTime -gt $t0 } | Select-Object -First 1
}
if (-not $stats) { Say 'O jogo nao gerou a lista em 30 s. O jogo foi aberto por este script? Mande a pasta diag.' 'Red'; Note 'sem draw_stats'; Read-Host 'ENTER'; exit 1 }
$cands = @(Get-Content $stats.FullName | ForEach-Object { if ($_ -match '^(draw|mesh|args|pointed)\s+([0-9a-f]{16})\b') { $Matches[2] } } |
    Where-Object { $base -notcontains $_ } | Select-Object -Unique)
Note "lista: $($stats.Name), $($cands.Count) shaders de desenho"
Say "$($cands.Count) shaders de desenho na cena. Comecando a busca." 'Green'
Say 'Em cada rodada: jogue ~1 minuto, girando a camera. Partes da cena vao sumir (normal). Olhe so se a COR da cena pisca.' 'Cyan'

$round = 0
while ($cands.Count -gt 1) {
    $round++
    $half = [int][math]::Ceiling($cands.Count / 2)
    $hidden = @($cands[0..($half - 1)])
    $shown = @($cands[$half..($cands.Count - 1)])
    Write-Skip $hidden
    Say ''
    Say "Rodada $round : $($hidden.Count) shaders escondidos, $($cands.Count) suspeitos no total." 'Yellow'
    $a = Ask 'Ainda PISCA? s = sim, n = nao, x = a tela ficou estranha demais para ver' @('s','n','x')
    if ($a -eq 'x') {   # (esconde a outra metade e pergunta de novo)
        Write-Skip $shown
        $b = Ask 'Escondi a OUTRA metade. Ainda PISCA? s = sim, n = nao' @('s','n')
        Note "rodada $round : outra metade escondida ($($shown.Count)) -> $b"
        $cands = if ($b -eq 'n') { $shown } else { $hidden }
    } else {
        Note "rodada $round : $($hidden.Count) escondidos -> $a"
        $cands = if ($a -eq 'n') { $hidden } else { $shown }
    }
}

# a confirmacao: so ele escondido
$key = $cands[0]
Write-Skip @($key)
Say ''
Say "Suspeito: $key (so ele escondido agora)." 'Green'
$c = Ask 'Com SO ele escondido, ainda PISCA? s = sim, n = nao' @('s','n')
Note "suspeito $key; so ele escondido -> $c"
if ($c -eq 'n') {
    Say "ACHADO: o shader $key causa o flicker." 'Green'
    Add-Content (Join-Path $diag 'resultado.txt') "shader do flicker: $key (lista $($stats.Name))"
} else {
    Say 'Escondendo so ele ainda pisca: a causa nao e um desenho so (pode ser um compute, como a neblina).' 'Yellow'
    Add-Content (Join-Path $diag 'resultado.txt') "inconclusivo: ultimo suspeito $key ainda pisca sozinho (lista $($stats.Name))"
}
Copy-Item $bak $skip -Force; Remove-Item $bak
Note 'fim; pular-shaders.txt restaurado'
Say ''
Say 'Pronto. O pular-shaders.txt voltou ao original.' 'Green'
Say "Mande a pasta diag inteira (zipada): $diag" 'Cyan'
Read-Host 'ENTER para sair'

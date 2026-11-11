# medir-rodada.ps1 - resume o desempenho de uma rodada a partir do log (somente leitura, nao abre o jogo)
# Ideia inspirada no medir-partida.ps1 do ocarina-recomp (GPL-3.0); codigo escrito do zero para o log do Hookshot.
#   powershell -ExecutionPolicy Bypass -File C:\DEV\medir-rodada.ps1                  a ultima rodada de C:\DEV\rodadas
#   powershell -ExecutionPolicy Bypass -File C:\DEV\medir-rodada.ps1 -Log <arquivo>   um log qualquer
#   powershell -ExecutionPolicy Bypass -File C:\DEV\medir-rodada.ps1 -Comparar        todas as rodadas, uma linha cada
#   -Saida <arquivo> grava o texto do resumo
param([string]$Log, [switch]$Comparar, [string]$Saida)

$inv = [Globalization.CultureInfo]::InvariantCulture
function Num($s) { return [double]::Parse($s, $inv) }
$Dir = 'C:\DEV\rodadas'

function Ler([string]$caminho) {
    $r = [ordered]@{
        Arquivo = [IO.Path]::GetFileName($caminho); Config = ''; Amostras = 0; SomaFps = 0.0; Abaixo55 = 0; Abaixo40 = 0
        Janelas = 0; PiorQuadro = 0.0; Acima50 = 0; Acima100 = 0; VramMax = 0.0; VramTotal = 0.0
        Lentos = 0; PiorLento = 0.0; PiorUpload = 0.0; Adiadas = 0; NaoLigado = 0; Estouros = 0; Limite = 0
        Fatais = @(); Texturas = ''; Resolucao = ''; GeracaoQuadros = ''; Reflex = ''; Nota = ''
    }
    $fs = [IO.File]::Open($caminho, 'Open', 'Read', 'ReadWrite')
    $sr = New-Object IO.StreamReader($fs)
    while ($null -ne ($l = $sr.ReadLine())) {
        if ($l -match 'presents, ([\d.]+) fps') {
            $f = Num $Matches[1]; $r.Amostras++; $r.SomaFps += $f
            if ($f -lt 55) { $r.Abaixo55++ }
            if ($f -lt 40) { $r.Abaixo40++ }
        }
        elseif ($l -match 'status: \d+ frames, the slowest ([\d.]+) ms; VRAM ([\d.]+) of ([\d.]+) GB') {
            $ms = Num $Matches[1]; $v = Num $Matches[2]; $r.Janelas++; $r.VramTotal = Num $Matches[3]
            if ($ms -gt $r.PiorQuadro) { $r.PiorQuadro = $ms }
            if ($ms -gt 50) { $r.Acima50++ }
            if ($ms -gt 100) { $r.Acima100++ }
            if ($v -gt $r.VramMax) { $r.VramMax = $v }
        }
        elseif ($l -match 'slow submit: ([\d.]+) ms') {
            $r.Lentos++; $ms = Num $Matches[1]; if ($ms -gt $r.PiorLento) { $r.PiorLento = $ms }
        }
        elseif ($l -match "a frame's uploads took ([\d.]+) ms") {
            $ms = Num $Matches[1]; if ($ms -gt $r.PiorUpload) { $r.PiorUpload = $ms }
        }
        elseif ($l -match '(\d+) so far\)') { $n = [int]$Matches[1]; if ($n -gt $r.Adiadas) { $r.Adiadas = $n } }
        elseif ($l -match 'storage buffer NOT bound') { $r.NaoLigado++ }
        elseif ($l -match 'wait for write-back .* timed out') { $r.Estouros++ }
        elseif ($l -match "over the driver's video-memory allowance") { $r.Limite++ }
        elseif ($l -match 'textures (\d+) MB \(budget (\d+) MB\), (\d+) textures') { $r.Texturas = ('{0} MB em {2} texturas (orcamento {1} MB)' -f $Matches[1], $Matches[2], $Matches[3]) }
        elseif ($l -match 'frame interpolation ready: (.+)$') { $r.GeracaoQuadros = $Matches[1].Trim() }
        elseif ($l -match 'NVIDIA Reflex: (on|off)(.*)$') { $r.Reflex = ($Matches[1] + $Matches[2]).Trim() }
        elseif ($l -match '###\s*NOTA: (.+)$') { $r.Nota = $Matches[1].Trim() }
        elseif ($l -match 'fsr3: (\d+x\d+) -> (\d+x\d+)') { $r.Resolucao = ('{0} -> {1} (FSR 3.1)' -f $Matches[1], $Matches[2]) }
        elseif ($l -match '(?i)device lost|\bFATAL\b|\bcrash(ed)?\b') { if ($r.Fatais.Count -lt 3) { $r.Fatais += $l.Trim() } }
        elseif ($l -match 'VRAM=(.+?)(\s*###|$)' -and $l -match '###') { $r.Config = $Matches[1].Trim() }
    }
    $sr.Close(); $fs.Close()
    return [pscustomobject]$r
}

function Fps($r) { if ($r.Amostras) { return [math]::Round($r.SomaFps / $r.Amostras, 1) } else { return 0 } }

function Resumo($r) {
    $o = @()
    $o += "== Rodada: $($r.Arquivo)"
    if ($r.Config) { $o += "Configuracao: $($r.Config)" }
    if ($r.Nota) { $o += "Nota do jogador: $($r.Nota)" }
    if ($r.Resolucao) { $o += "Resolucao: $($r.Resolucao)" }
    if ($r.GeracaoQuadros) { $o += "Geracao de quadros: $($r.GeracaoQuadros)" } else { $o += 'Geracao de quadros: desligada' }
    if ($r.Reflex) { $o += "NVIDIA Reflex: $($r.Reflex)" }
    $o += ("Fps apresentados (amostras a cada 120 quadros): media {0}; abaixo de 55: {1} de {2}; abaixo de 40: {3}" -f (Fps $r), $r.Abaixo55, $r.Amostras, $r.Abaixo40)
    $o += '  (com geracao de quadros ligada, esses fps incluem os quadros gerados)'
    $o += ("Pior quadro por janela de 600: {0} ms; janelas acima de 50 ms: {1}; acima de 100 ms: {2} (de {3})" -f $r.PiorQuadro, $r.Acima50, $r.Acima100, $r.Janelas)
    $o += ("Memoria de video: pico {0} GB de {1} GB; texturas: {2}" -f $r.VramMax, $r.VramTotal, $r.Texturas)
    $o += ("Pausas lentas registradas: {0}, a pior de {1} ms; maior upload de texturas num quadro: {2} ms" -f $r.Lentos, $r.PiorLento, $r.PiorUpload)
    $o += ("Texturas ASTC adiadas: {0}" -f $r.Adiadas)
    $o += ("Buffer sem conexao (o log guarda so os 40 primeiros): {0}" -f $r.NaoLigado)
    $o += ("Esperas de escrita estouradas: {0}; estouro do limite de VRAM do driver: {1}" -f $r.Estouros, $r.Limite)
    if ($r.Fatais.Count -gt 0) { $o += 'Erros graves:'; $o += $r.Fatais } else { $o += 'Erros graves: nenhum' }
    return $o
}

$out = @()
if ($Comparar) {
    $arqs = @(Get-ChildItem $Dir -Filter 'rodada-*.txt' -ErrorAction SilentlyContinue | Sort-Object Name)
    if ($arqs.Count -eq 0) { Write-Host "Nenhuma rodada em $Dir"; exit 1 }
    $rows = foreach ($a in $arqs) {
        $r = Ler $a.FullName
        [pscustomobject]@{ Rodada = $r.Arquivo -replace '\.txt$',''; FpsMedio = (Fps $r); Abaixo55 = $r.Abaixo55; PiorQuadroMs = $r.PiorQuadro
            Acima50 = $r.Acima50; Acima100 = $r.Acima100; VramMaxGB = $r.VramMax; Adiadas = $r.Adiadas; NaoLigado = $r.NaoLigado }
    }
    $out = ($rows | Format-Table -AutoSize | Out-String).TrimEnd() -split "`r?`n"
} else {
    if (-not $Log) {
        $ult = Get-ChildItem $Dir -Filter 'rodada-*.txt' -ErrorAction SilentlyContinue | Sort-Object Name | Select-Object -Last 1
        if ($ult) { $Log = $ult.FullName } else { $gd = 'C:\Games\RecompZel'; if (-not (Test-Path $gd)) { $gd = 'C:\Games\HookshotDev' }; $Log = Join-Path $gd 'hookshot_log.txt' }
    }
    if (-not (Test-Path $Log)) { Write-Host "Nao achei o log: $Log"; exit 1 }
    $out = Resumo (Ler $Log)
}
$out | ForEach-Object { Write-Host $_ }
if ($Saida) { $out | Set-Content -Path $Saida -Encoding UTF8 }

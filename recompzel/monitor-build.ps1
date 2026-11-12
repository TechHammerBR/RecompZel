# monitor-build.ps1
# Le C:\DEV\build.log (somente leitura) e mostra o progresso real do build.
# Uso:  powershell -ExecutionPolicy Bypass -File C:\DEV\monitor-build.ps1        (uma vez)
#       powershell -ExecutionPolicy Bypass -File C:\DEV\monitor-build.ps1 -Watch (atualiza a cada 10 s)
# Nao altera nem apaga nada. Salva o resultado em C:\DEV\progress-report.txt

param([switch]$Watch, [int]$Interval = 10)

$Log      = Join-Path $PSScriptRoot 'build.log'
$Work     = Join-Path $PSScriptRoot 'build-work'
$Report   = Join-Path $PSScriptRoot 'progress-report.txt'

# Pesos de cada etapa no total (soma 100). Ajuste se medir tempos reais.
$W = @{ read = 15; lift = 10; compile = 60; finish = 15 }

# Total de arquivos da romfs do update (do proprio log: "romfs 186583 files")
$TotalFilesDefault = 186583

function Read-LogLines {
    if (-not (Test-Path $Log)) { return @() }
    $fs = [System.IO.File]::Open($Log, 'Open', 'Read', 'ReadWrite')
    $sr = New-Object System.IO.StreamReader($fs)
    $txt = $sr.ReadToEnd(); $sr.Close(); $fs.Close()
    return $txt -split "`r?`n"
}

function Bar([double]$pct) {
    $n = [int]([math]::Round([math]::Min(100,[math]::Max(0,$pct)) / 5))
    return '[' + ('#' * $n) + ('-' * (20 - $n)) + ']'
}

function Show-Progress {
    $lines = Read-LogLines
    if ($lines.Count -eq 0) { Write-Host "build.log nao encontrado ou vazio: $Log"; return }

    $stage = 'inicio'; $readPct = 0; $liftPct = 0; $compPct = 0; $finPct = 0
    $totalFiles = $TotalFilesDefault; $filesDone = 0; $mib = 0
    $planTotal = 0; $prog = -1; $eta = $null; $err = @(); $done = $false

    foreach ($l in $lines) {
        if ($l -match '^@@stage\s+(\S+)') { $stage = $Matches[1] }
        if ($l -match 'title 1 .*romfs\s+(\d+)\s+files') { $totalFiles = [int]$Matches[1] }
        if ($l -match '^\s*([\d\.]+)\s+MiB written \((\d+) files completed\)') { $mib = [double]$Matches[1]; $filesDone = [int]$Matches[2] }
        if ($l -match '^done:\s+(\d+)\s+files written') { $filesDone = [int]$Matches[1] }
        if ($l -match '^@@plan\s+(\d+)') { $planTotal = [int]$Matches[1] }
        if ($l -match '^@@progress\s+([\d\.]+)') { $prog = [double]$Matches[1] }
        if ($l -match '^@@eta\s+(\d+)')  { $eta = [int]$Matches[1] }
        if (($l -match '^(error|fatal)\b') -or ($l -match 'Traceback') -or ($l -match '(?i)Terminou com codigo [1-9]') -or ($l -match '^compiled in .*,\s*[1-9]\d* failed')) { $err += $l }
        if ($l -match '(?i)^@@done|^@@stage\s+done|^the build took|build complete|build finished') { $done = $true }
    }

    # Leitura do jogo
    if ($stage -eq 'read') { $readPct = [math]::Min(100, 100.0 * $filesDone / $totalFiles) } else { $readPct = 100 }
    if ($stage -eq 'inicio') { $readPct = 0 }

    # Traducao (lift): sem contador, so 0 ou 100
    if ($stage -in @('compile','link','shaders','pack','finish') -or $stage -notin @('inicio','read','lift')) { $liftPct = 100 }

    # Compilacao: conta objetos (.o/.obj) em build-work e compara com o plano
    $objs = 0
    if ($prog -ge 0) { $compPct = [math]::Min(100, 100.0 * $prog); $objs = [int][math]::Round($prog * $planTotal) }
    if ($stage -notin @('inicio','read','lift','compile')) { $compPct = 100 }

    if ($done) { $finPct = 100 } elseif ($stage -notin @('inicio','read','lift','compile')) { $finPct = 50 }

    $total = ($readPct*$W.read + $liftPct*$W.lift + $compPct*$W.compile + $finPct*$W.finish) / 100.0

    function Mark([double]$p, [string]$cur) {
        if ($p -ge 100) { return '[OK]' }
        if ($stage -eq $cur) { return '[>>]' }
        return '[  ]'
    }

    $pctInt = [int][math]::Floor($total)
    if ($done) { $pctInt = 100 }
    if ($err.Count -gt 0) { $status = 'COM ERRO (veja abaixo)' }
    elseif ($done) { $status = 'PRONTO' }
    else { $status = 'EM ANDAMENTO' }

    $out = @()
    $out += ''
    $out += "   RECOMP ZELDA OoT: $pctInt% concluido"
    $out += "   $(Bar $total)  $status"
    $out += ''
    $out += ("   {0} 1. Ler o jogo           {1,3:N0}%" -f (Mark $readPct 'read'), $readPct)
    $out += ("   {0} 2. Traduzir para PC     {1,3:N0}%" -f (Mark $liftPct 'lift'), $liftPct)
    $out += ("   {0} 3. Montar o programa    {1,3:N0}%   ({2} de {3} pecas)" -f (Mark $compPct 'compile'), $compPct, $objs, $planTotal)
    $out += ("   {0} 4. Finalizar e empacotar {1,3:N0}%" -f (Mark $finPct 'finish'), $finPct)
    $out += ''
    if ($err.Count -gt 0) { $out += 'Erros no log:'; $out += ($err | Select-Object -Last 5) }
    $out += "Atualizado em $(Get-Date -Format 'dd/MM HH:mm:ss'). Percentual total e uma estimativa (pesos: 15/10/60/15)."

    $out | ForEach-Object { Write-Host $_ }
    $out | Set-Content -Path $Report -Encoding UTF8
}

if ($Watch) {
    while ($true) { Clear-Host; Show-Progress; Start-Sleep -Seconds $Interval }
} else {
    Show-Progress
}

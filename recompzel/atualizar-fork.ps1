# atualizar-fork.ps1 - traz as novidades do Hookshot original (NotRexed) para o nosso fork local em D:\PSN nativo\ZELDA OCT\RecompZel-main\DEV\RecompZel
# Sem -Aplicar: so mostra o que mudou. Com -Aplicar: atualiza (junta o upstream; se der conflito, desfaz tudo). Nao apaga nada.
# Com -Aplicar -Enviar: depois de atualizar, envia o resultado para o nosso fork no GitHub (origin). So commits sao enviados.
#   powershell -ExecutionPolicy Bypass -File D:\PSN nativo\ZELDA OCT\RecompZel-main\DEV\atualizar-fork.ps1
#   powershell -ExecutionPolicy Bypass -File D:\PSN nativo\ZELDA OCT\RecompZel-main\DEV\atualizar-fork.ps1 -Aplicar
param([switch]$Aplicar, [switch]$Enviar)

$Repo = if ((Split-Path $PSScriptRoot -Leaf) -eq 'recompzel' -and (Test-Path (Join-Path (Split-Path $PSScriptRoot -Parent) 'nx2\make_game.py'))) { Split-Path $PSScriptRoot -Parent } else { 'D:\PSN nativo\ZELDA OCT\RecompZel-main\DEV\RecompZel' }
Set-Location $Repo
git config core.fileMode false

$tem = git remote 2>$null | Where-Object { $_ -eq 'upstream' }
if (-not $tem) { git remote add upstream https://github.com/NotRexed/Hookshot.git }

Write-Host 'Buscando as novidades do Hookshot original...'
git fetch upstream main 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { Write-Host 'Falha ao buscar. Verifique a internet e tente de novo.'; exit 1 }

$novos = @(git log --oneline HEAD..upstream/main)
Write-Host ("Commits novos no Hookshot original: {0}" -f $novos.Count)
$novos | Select-Object -First 30 | ForEach-Object { Write-Host ('  ' + $_) }

if ($novos.Count -eq 0) { Write-Host 'Seu fork ja esta atualizado.'; exit 0 }
if (-not $Aplicar) { Write-Host ''; Write-Host 'Para aplicar: rode o mesmo comando com -Aplicar'; exit 0 }

$sujo = @(git status --porcelain --untracked-files=no)
if ($sujo.Count -gt 0) {
    Write-Host 'Ha arquivos modificados no fork. Nao vou atualizar por cima deles:'
    $sujo | ForEach-Object { Write-Host ('  ' + $_) }
    exit 1
}

git merge --no-edit upstream/main
if ($LASTEXITCODE -ne 0) { git merge --abort 2>$null; Write-Host 'Houve conflito com o Hookshot original. Desfiz a juncao: nada foi alterado. Me mande esta saida.'; exit 1 }

Write-Host ''
Write-Host 'Fork atualizado. Proximo passo: rode build-game.ps1 (so recompila o que mudou).'

if ($Enviar) {
    Write-Host 'Enviando para o seu fork no GitHub (origin)...'
    git push origin HEAD
    if ($LASTEXITCODE -ne 0) { Write-Host 'Nao foi possivel enviar. O fork local esta atualizado; me mande esta saida.' }
    else { Write-Host 'Enviado.' }
}

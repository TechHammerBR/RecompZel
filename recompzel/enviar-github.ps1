# enviar-github.ps1  -  Espelha no GitHub tudo o que foi alterado localmente (codigo do jogo e ferramentas do projeto).
# Uso: powershell -ExecutionPolicy Bypass -File C:\DEV\enviar-github.ps1
#      (opcional) -Mensagem "texto do commit"
# O que faz: copia os scripts de C:\DEV para a pasta recompzel\ do repositorio, faz commit de tudo e envia (push).
# Nao apaga nada. Se nao houver mudanca, nao faz nada.
param([string]$Mensagem = 'RecompZel: atualiza launcher, FSR 4 direto e ferramentas do projeto')

$ErrorActionPreference = 'Continue'
$Repo  = 'C:\DEV\RecompZel'
$Tools = Join-Path $Repo 'recompzel'
$Files = 'launcher.ps1','medir-rodada.ps1','atualizar-fork.ps1','build-game.ps1','criar-atalhos.ps1','monitor-build.ps1','env-recompzel.ps1','enviar-github.ps1','post-install.ps1','instalar.ps1','recompzel.ico','games.json'

if (-not (Test-Path (Join-Path $Repo '.git'))) { Write-Host "Nao achei o repositorio em $Repo"; return }
Set-Location $Repo
git config core.fileMode false

# 1. copia as ferramentas para dentro do repositorio
New-Item -ItemType Directory -Force -Path $Tools | Out-Null
foreach ($f in $Files) {
    $src = Join-Path 'C:\DEV' $f
    if (Test-Path $src) { Copy-Item $src (Join-Path $Tools $f) -Force }
}
$readme = Join-Path $Tools 'LEIA-ME.txt'
if (-not (Test-Path $readme)) {
    @(
        'RecompZel: ferramentas do projeto (launcher, build, medicao de rodadas, atalhos).',
        'Estes arquivos sao copiados de C:\DEV por enviar-github.ps1. Edite la e rode o script para atualizar aqui.',
        'Componentes de terceiros (por exemplo o fsr4vk, GPLv3) nunca ficam neste repositorio: o launcher baixa e confere o hash.'
    ) | Set-Content $readme -Encoding ASCII
}

# 2. mostra o que mudou
$st = @(git status --porcelain)
if ($st.Count -eq 0) { Write-Host 'Nada novo para enviar: o GitHub ja esta igual ao seu PC.'; return }
Write-Host 'Arquivos alterados:'
$st | ForEach-Object { Write-Host "  $_" }

# 3. commit (usa a identidade ja configurada; se nao houver, usa uma generica so para este commit)
$nome  = (git config user.name)
$email = (git config user.email)
$id = @()
if (-not $nome -or -not $email) { $id = @('-c', 'user.name=RecompZel', '-c', 'user.email=recompzel@users.noreply.github.com') }
$msg = $Mensagem + "`n`nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`nClaude-Session: https://claude.ai/code/session_01FUQGXcBcf8hNKFjvRiFtfL"
git add -A
git @id commit -m $msg
if ($LASTEXITCODE -ne 0) { Write-Host 'O commit falhou. Veja a mensagem acima.'; return }

# 4. envia
git push origin HEAD
if ($LASTEXITCODE -ne 0) {
    Write-Host 'O envio foi recusado. Tentando integrar as mudancas do GitHub e enviar de novo...'
    git pull --rebase origin HEAD
    if ($LASTEXITCODE -eq 0) { git push origin HEAD }
}
if ($LASTEXITCODE -eq 0) { Write-Host 'Pronto: o GitHub esta atualizado.' } else { Write-Host 'Nao consegui enviar. Copie esta janela e mande para o suporte.' }

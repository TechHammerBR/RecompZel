# Prepara o ambiente de build usando as ferramentas que o HookshotBuilder ja instalou.
# Nao e para rodar sozinho: os outros scripts chamam este com ". C:\DEV\env-recompzel.ps1"
$Repo = 'C:\DEV\RecompZel'
$ver = Get-ChildItem "$env:LOCALAPPDATA\HookshotBuilder\versions" -Directory |
       Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $ver) { throw "HookshotBuilder nao encontrado em $env:LOCALAPPDATA\HookshotBuilder\versions" }
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

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$existingSessionPython = Join-Path $PSScriptRoot '..\..\work\paperagent-venv\Scripts\python.exe'
if (Test-Path -LiteralPath '.venv\Scripts\python.exe') {
    $appPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
} elseif (Test-Path -LiteralPath $existingSessionPython) {
    $appPython = (Resolve-Path -LiteralPath $existingSessionPython).Path
} else {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12+ is required.' }
    $appPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
}
& $appPython -c 'import streamlit, fastembed, pypdf, numpy'
if ($LASTEXITCODE -ne 0) {
    & $appPython -m pip install -r requirements-workbench.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
}
if (-not (Test-Path -LiteralPath '.cache\models\fast-all-MiniLM-L6-v2\model.onnx')) {
    & $appPython scripts/download_model.py
    if ($LASTEXITCODE -ne 0) { throw 'Model download failed. BM25 mode remains available.' }
}
& $appPython -m streamlit run enhanced_app.py --server.address 127.0.0.1 --browser.gatherUsageStats false

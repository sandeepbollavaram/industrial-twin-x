# Dot-source before running uv: . .\scripts\env.ps1
# Keeps uv's cache and interpreters off C: for this shell only; nothing persists.
if (Test-Path 'D:\') {
    $env:UV_CACHE_DIR = 'D:\uv-cache'
    $env:UV_PYTHON_INSTALL_DIR = 'D:\uv-python'
}
$env:UV_LINK_MODE = 'copy'

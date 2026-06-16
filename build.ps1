# ============================================================
#  TodoApp 配布ビルドスクリプト
# ------------------------------------------------------------
#  実行: PowerShell で  .\build.ps1
#
#  処理内容:
#    1. PyInstaller で dist\TodoApp\TodoApp.exe を生成（Python 同梱）
#    2. Inno Setup があれば Output\TodoApp_Setup.exe を生成
#       （iscc が PATH に無い場合は手順を案内してスキップ）
# ============================================================
$ErrorActionPreference = "Stop"
$Python = "C:\Users\hachi\AppData\Local\Python\bin\python.exe"

Write-Host "[1/2] PyInstaller でアプリをビルドしています..." -ForegroundColor Cyan
& $Python -m PyInstaller --noconfirm TodoApp.spec
if (-not (Test-Path "dist\TodoApp\TodoApp.exe")) {
    throw "ビルドに失敗しました（TodoApp.exe が見つかりません）。"
}
Write-Host "  -> dist\TodoApp\TodoApp.exe を生成しました。" -ForegroundColor Green

Write-Host "[2/2] インストーラーを作成しています..." -ForegroundColor Cyan
# iscc (Inno Setup コンパイラ) を探す
$iscc = (Get-Command iscc -ErrorAction SilentlyContinue).Source
if (-not $iscc) {
    foreach ($p in @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles}\Inno Setup 6\ISCC.exe",
        "${env:LOCALAPPDATA}\Programs\Inno Setup 6\ISCC.exe"
    )) { if (Test-Path $p) { $iscc = $p; break } }
}

if (-not $iscc) {
    Write-Host "  Inno Setup (iscc) が見つかりませんでした。インストーラー生成をスキップします。" -ForegroundColor Yellow
    Write-Host "  Inno Setup を入れるには:  winget install JRSoftware.InnoSetup" -ForegroundColor Yellow
    Write-Host "  導入後に再度 .\build.ps1 を実行してください。" -ForegroundColor Yellow
    return
}

if (-not (Test-Path "redist\AccessDatabaseEngine_X64.exe")) {
    Write-Host "  注意: redist\AccessDatabaseEngine_X64.exe がありません。" -ForegroundColor Yellow
    Write-Host "        Access ドライバの自動導入なしでインストーラーを作成します。" -ForegroundColor Yellow
    Write-Host "        同梱したい場合は Microsoft 公式 (Access Database Engine 2016 再頒布可能)" -ForegroundColor Yellow
    Write-Host "        から取得して redist\ に置いてください。" -ForegroundColor Yellow
}

& $iscc "installer.iss"
Write-Host "  -> Output\TodoApp_Setup.exe を生成しました。" -ForegroundColor Green
Write-Host "完了。" -ForegroundColor Green

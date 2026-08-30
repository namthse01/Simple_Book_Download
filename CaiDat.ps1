# =============================================================
#  DCR - DragonCloud_reading : cai dat
#  Cai thu vien can thiet + tao shortcut ngoai Desktop.
#  Chay 1 lan:  powershell -ExecutionPolicy Bypass -File CaiDat.ps1
#  (hoac nhay dup CaiDat.bat)
# =============================================================

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$TEN  = 'DCReading'
$MOTA = 'DCR - DragonCloud_reading'

function Say($m) { Write-Host $m -ForegroundColor Cyan }
function Ok($m)  { Write-Host ('  [OK] ' + $m) -ForegroundColor Green }
function Bad($m) { Write-Host ('  [!] ' + $m) -ForegroundColor Yellow }

# ---- 1. Tim Python ----
Say 'Dang tim Python...'
$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { $python = (Get-Command py -ErrorAction SilentlyContinue).Source }
if (-not $python) {
    Write-Host 'Khong tim thay Python. Cai tai https://python.org roi chay lai.' -ForegroundColor Red
    Read-Host 'Enter de thoat'
    exit 1
}
# pythonw.exe chay khong kem cua so lenh -> bam shortcut la ra app luon
$pythonw = Join-Path (Split-Path $python) 'pythonw.exe'
if (-not (Test-Path $pythonw)) { $pythonw = $python; Bad 'Khong co pythonw.exe, se hien cua so lenh khi chay' }
Ok $python

# ---- 2. Thu vien ----
Say 'Dang cai thu vien can thiet...'
& $python -m pip install --quiet --disable-pip-version-check requests beautifulsoup4 lxml pywebview
if ($LASTEXITCODE -ne 0) { Bad 'pip bao loi - thu chay lai lenh pip thu cong de xem chi tiet' }
else { Ok 'requests, beautifulsoup4, lxml, pywebview' }

# ---- 3. Shortcut ----
Say 'Dang tao shortcut...'
$icon = Join-Path $root 'appicon.ico'
$target = Join-Path $root 'app.py'
$ws = New-Object -ComObject WScript.Shell

function New-Loi($duongDan) {
    $lnk = $ws.CreateShortcut($duongDan)
    $lnk.TargetPath       = $pythonw
    $lnk.Arguments        = '"' + $target + '"'
    $lnk.WorkingDirectory = $root
    if (Test-Path $icon) { $lnk.IconLocation = $icon + ',0' }
    $lnk.Description      = $MOTA
    $lnk.Save()
}

$desktop = Join-Path ([Environment]::GetFolderPath('Desktop')) ($TEN + '.lnk')
New-Loi $desktop
Ok ('Desktop: ' + $TEN)

$menu = Join-Path ([Environment]::GetFolderPath('Programs')) ($TEN + '.lnk')
try { New-Loi $menu; Ok ('Menu Start: ' + $TEN) } catch { Bad 'Khong tao duoc muc trong Menu Start' }

Write-Host ''
Write-Host ('XONG! Nhay dup shortcut "' + $TEN + '" tren Desktop de mo app.') -ForegroundColor Green
Write-Host 'Neu bam ma khong thay gi, xem file data\loi_khoi_dong.txt' -ForegroundColor DarkGray
Write-Host ''
Read-Host 'Enter de dong'

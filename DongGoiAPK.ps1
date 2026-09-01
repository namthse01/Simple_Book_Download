# =============================================================
#  DCReader : dong goi lai file APK sau khi sua code trong mobile\
#  Chay:  powershell -ExecutionPolicy Bypass -File DongGoiAPK.ps1
#  Can: da chay CaiDat.bat (Node) + bo cong cu Android o D:\tool\android-build
#  (JDK 21 + Android SDK - phien lam viec dau tien da tai san)
# =============================================================
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

$env:JAVA_HOME = 'D:\tool\android-build\jdk-21.0.12.1+1'
if (-not (Test-Path $env:JAVA_HOME)) {
    Write-Host 'Khong thay JDK o D:\tool\android-build - xem README muc DCReader.' -ForegroundColor Red
    exit 1
}

Write-Host '1) Chep giao dien tu mobile\ vao vo APK...' -ForegroundColor Cyan
Copy-Item (Join-Path $root 'mobile\*') (Join-Path $root 'apk\www\') -Force

Write-Host '2) Dong bo Capacitor...' -ForegroundColor Cyan
Set-Location (Join-Path $root 'apk')
npx cap sync android | Out-Null

Write-Host '3) Build APK (lan dau hoi lau)...' -ForegroundColor Cyan
Set-Location (Join-Path $root 'apk\android')
& .\gradlew.bat assembleDebug
if ($LASTEXITCODE -ne 0) { Write-Host 'Build loi - doc thong bao ben tren.' -ForegroundColor Red; exit 1 }

$apk = Join-Path $root 'apk\android\app\build\outputs\apk\debug\app-debug.apk'
$dich = Join-Path $root 'DCReader.apk'
Copy-Item $apk $dich -Force
Write-Host ("XONG! File: " + $dich) -ForegroundColor Green
Write-Host 'Chep file nay sang dien thoai (Zalo/USB/Drive) roi bam vao de cai.'

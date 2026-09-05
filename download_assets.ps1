# ==============================================================================
# Script: download_assets.ps1
# Purpose: Download Ubuntu 24.04, 22.04, 20.04 ISOs and extract netboot kernels
# ==============================================================================

[CmdletBinding()]
param(
    [string]$DataDir = ".\data"
)

$ErrorActionPreference = "Stop"

$IsoDir = Join-Path $DataDir "iso"
$NetbootDir = Join-Path $DataDir "netboot"

# Ensure directories exist
@($IsoDir, (Join-Path $NetbootDir "ubuntu-24.04"), (Join-Path $NetbootDir "ubuntu-22.04"), (Join-Path $NetbootDir "ubuntu-20.04")) | ForEach-Object {
    if (-not (Test-Path $_)) {
        New-Item -ItemType Directory -Path $_ -Force | Out-Null
    }
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " Ubuntu PXE Asset Downloader (PowerShell)" -ForegroundColor Cyan
Write-Host " Target ISO Directory:     $IsoDir" -ForegroundColor Gray
Write-Host " Target Netboot Directory: $NetbootDir" -ForegroundColor Gray
Write-Host "==========================================================" -ForegroundColor Cyan

function Download-And-Extract {
    param(
        [string]$Ver,
        [string]$IsoUrl,
        [string]$IsoFile
    )

    $TargetDir = Join-Path $NetbootDir $Ver
    $IsoPath = Join-Path $IsoDir $IsoFile

    Write-Host "`n>>> Processing $Ver ($IsoFile)..." -ForegroundColor Yellow

    # Check if ISO exists
    $existing = Get-ChildItem -Path $IsoDir -Filter "$Ver*.iso" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($existing) {
        Write-Host "Found existing ISO: $($existing.FullName) (skipping download)" -ForegroundColor Green
        $IsoPath = $existing.FullName
    } else {
        Write-Host "Downloading $IsoFile from $IsoUrl..." -ForegroundColor Cyan
        if (Get-Command curl.exe -ErrorAction SilentlyContinue) {
            & curl.exe -L --progress-bar -o $IsoPath $IsoUrl
        } else {
            Start-BitsTransfer -Source $IsoUrl -Destination $IsoPath
        }
    }

    $vmlinuz = Join-Path $TargetDir "vmlinuz"
    $initrd = Join-Path $TargetDir "initrd"

    if ((Test-Path $vmlinuz) -and (Test-Path $initrd)) {
        Write-Host "Netboot kernel and initrd already extracted in $TargetDir" -ForegroundColor Green
        return
    }

    Write-Host "Extracting casper/vmlinuz and casper/initrd..." -ForegroundColor Cyan

    $extracted = $false

    # Method 1: Mount-DiskImage (Native Windows, zero extra tools)
    try {
        $mounted = Mount-DiskImage -ImagePath (Resolve-Path $IsoPath) -PassThru -ErrorAction Stop
        $driveLetter = ($mounted | Get-Volume -ErrorAction SilentlyContinue).DriveLetter
        if ($driveLetter) {
            $srcCasper = "$($driveLetter):\casper"
            if (Test-Path "$srcCasper\vmlinuz") {
                Copy-Item "$srcCasper\vmlinuz" -Destination $vmlinuz -Force
            }
            if (Test-Path "$srcCasper\initrd") {
                Copy-Item "$srcCasper\initrd" -Destination $initrd -Force
            }
            Dismount-DiskImage -ImagePath (Resolve-Path $IsoPath) -ErrorAction SilentlyContinue
            if ((Test-Path $vmlinuz) -and (Test-Path $initrd)) {
                $extracted = $true
                Write-Host "Extracted successfully via native Disk Mount!" -ForegroundColor Green
            }
        }
    } catch {
        # Fallback to tar or 7z if Mount-DiskImage requires admin elevation
    }

    # Method 2: tar.exe (bsdtar with ISO support)
    if (-not $extracted -and (Get-Command tar.exe -ErrorAction SilentlyContinue)) {
        try {
            & tar.exe -xf $IsoPath -C $TargetDir --strip-components 1 casper/vmlinuz casper/initrd 2>$null
            if ((Test-Path $vmlinuz) -and (Test-Path $initrd)) {
                $extracted = $true
                Write-Host "Extracted successfully via tar.exe!" -ForegroundColor Green
            }
        } catch {}
    }

    # Method 3: 7z.exe
    if (-not $extracted -and (Get-Command 7z -ErrorAction SilentlyContinue)) {
        try {
            & 7z e -y $IsoPath "-o$TargetDir" casper/vmlinuz casper/initrd | Out-Null
            if ((Test-Path $vmlinuz) -and (Test-Path $initrd)) {
                $extracted = $true
                Write-Host "Extracted successfully via 7z!" -ForegroundColor Green
            }
        } catch {}
    }

    if (-not $extracted) {
        Write-Warning "Could not extract kernel/initrd automatically. You can extract 'casper/vmlinuz' and 'casper/initrd' from the ISO into $TargetDir manually."
    }
}

# 1. Ubuntu 24.04 LTS (Noble Numbat)
Download-And-Extract -Ver "ubuntu-24.04" `
    -IsoUrl "https://releases.ubuntu.com/24.04/ubuntu-24.04.4-live-server-amd64.iso" `
    -IsoFile "ubuntu-24.04-live-server-amd64.iso"

# 2. Ubuntu 22.04 LTS (Jammy Jellyfish)
Download-And-Extract -Ver "ubuntu-22.04" `
    -IsoUrl "https://releases.ubuntu.com/22.04/ubuntu-22.04.5-live-server-amd64.iso" `
    -IsoFile "ubuntu-22.04-live-server-amd64.iso"

# 3. Ubuntu 20.04 LTS (Focal Fossa)
Download-And-Extract -Ver "ubuntu-20.04" `
    -IsoUrl "https://releases.ubuntu.com/20.04/ubuntu-20.04.6-live-server-amd64.iso" `
    -IsoFile "ubuntu-20.04-live-server-amd64.iso"

Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host " Asset preparation completed!" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green

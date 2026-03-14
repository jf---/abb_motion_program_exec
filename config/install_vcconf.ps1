# Install vcconf.xml and configure Windows Firewall for RobotStudio remote access.
# Run this script inside the Windows VM as Administrator.
#
# Usage (from Parallels shared folder):
#   powershell -ExecutionPolicy Bypass -File \\Mac\Home\...\config\install_vcconf.ps1

$ErrorActionPreference = "Stop"

$targetDir = "$env:APPDATA\ABB Industrial IT\Robotics IT\RobVC"
$targetFile = "$targetDir\vcconf.xml"
$sourceFile = Join-Path $PSScriptRoot "vcconf.xml"

# Create target directory
if (-not (Test-Path $targetDir)) {
    New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
    Write-Host "Created $targetDir"
}

# Copy vcconf.xml
Copy-Item -Path $sourceFile -Destination $targetFile -Force
Write-Host "Installed $targetFile"

# Add firewall rule for RWS (port 80) from Parallels subnet
$ruleName = "RobotStudio RWS (Parallels)"
$existing = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Firewall rule '$ruleName' already exists, skipping"
} else {
    New-NetFirewallRule `
        -DisplayName $ruleName `
        -Direction Inbound `
        -Protocol TCP `
        -LocalPort 80 `
        -RemoteAddress 10.211.55.0/24 `
        -Action Allow | Out-Null
    Write-Host "Created firewall rule '$ruleName'"
}

Write-Host ""
Write-Host "Done. Restart the virtual controller in RobotStudio to apply."

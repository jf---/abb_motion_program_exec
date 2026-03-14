#!/usr/bin/env bash
# Install vcconf.xml and firewall rule in a Parallels Windows VM.
# Requires: Parallels Desktop Pro/Business with prlctl.
#
# Usage: pixi run vm-setup
#        VM=<vm-name> pixi run vm-setup

set -euo pipefail

if ! command -v prlctl &>/dev/null; then
    echo "prlctl not found — requires Parallels Pro/Business"
    exit 1
fi

if [ -z "${VM:-}" ]; then
    mapfile -t vm_names < <(prlctl list --all --output name --no-header 2>/dev/null)

    if [ ${#vm_names[@]} -eq 0 ]; then
        echo "No Parallels VMs found."
        exit 1
    fi

    if [ ${#vm_names[@]} -eq 1 ]; then
        VM="${vm_names[0]}"
        echo "Using VM: $VM"
    else
        echo "Select a VM:"
        for i in "${!vm_names[@]}"; do
            echo "  $((i+1))) ${vm_names[$i]}"
        done
        printf "Enter number: "
        read -r choice
        if [[ ! "$choice" =~ ^[0-9]+$ ]] || [ "$choice" -lt 1 ] || [ "$choice" -gt ${#vm_names[@]} ]; then
            echo "Invalid selection."
            exit 1
        fi
        VM="${vm_names[$((choice-1))]}"
    fi
fi

# Verify the macOS host IP matches what vcconf.xml whitelists
repo_dir="$(cd "$(dirname "$0")/.." && pwd)"
vcconf="$repo_dir/config/vcconf.xml"
vcconf_ip=$(grep -oP 'host ip="\K[^"]+' "$vcconf" | head -1)
host_ip=$(ifconfig vnic0 2>/dev/null | awk '/inet / {print $2}')

if [ -n "$host_ip" ] && [ -n "$vcconf_ip" ] && [ "$host_ip" != "$vcconf_ip" ]; then
    echo "WARNING: macOS host IP ($host_ip) does not match vcconf.xml ($vcconf_ip)"
    echo "Update config/vcconf.xml with: <host ip=\"$host_ip\"/>"
    exit 1
fi

# Convert macOS absolute path to Parallels shared folder UNC path
# /Users/jelle/Code/... → \\Mac\Home\Code\...
relative="${repo_dir#$HOME/}"
win_path="\\\\Mac\\Home\\${relative//\//\\}\\config\\install_vcconf.ps1"

echo "Running install_vcconf.ps1 in VM '$VM'..."
prlctl exec "$VM" powershell -ExecutionPolicy Bypass -File "$win_path"

echo ""
echo "Done. Now restart the virtual controller in RobotStudio, then run:"
echo "  pixi run vm-verify"

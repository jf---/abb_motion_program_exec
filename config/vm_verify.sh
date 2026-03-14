#!/usr/bin/env bash
# Verify RWS connectivity to a RobotStudio virtual controller in a Parallels VM.
# Run this after vm_setup.sh and restarting the virtual controller.
#
# Usage: pixi run vm-verify
#        VM=<vm-name> pixi run vm-verify

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

# Get the VM's IP address
vm_ip=$(prlctl exec "$VM" powershell -Command "(Get-NetIPAddress -InterfaceAlias 'Parallels*' -AddressFamily IPv4).IPAddress" 2>/dev/null | tr -d '\r')

if [ -z "$vm_ip" ]; then
    echo "Could not detect VM IP — check that the VM is running."
    exit 1
fi

echo "VM IP: $vm_ip"
echo "Verifying RWS connection..."

if curl -sf -u "Default User:robotics" "http://$vm_ip/rw/system" -o /dev/null --connect-timeout 5; then
    echo "RWS is reachable at http://$vm_ip:80"
    echo ""
    echo "Connect from Python:"
    echo "  client = abb.MotionProgramExecClient(base_url=\"http://$vm_ip:80\")"
else
    echo "RWS not reachable at http://$vm_ip:80"
    echo ""
    echo "Checklist:"
    echo "  - Is the virtual controller running in RobotStudio?"
    echo "  - Did you restart it after installing vcconf.xml?"
    echo "  - Is Windows Firewall allowing TCP port 80?"
    exit 1
fi

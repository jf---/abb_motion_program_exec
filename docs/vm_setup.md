# Running RobotStudio in a Virtual Machine

RobotStudio is Windows-only. macOS and Linux users can run it in a virtual machine
and connect from the host. This requires two configuration steps inside the VM:

1. **RobotStudio**: whitelist the host IP for Robot Web Services (RWS)
2. **Windows Firewall**: allow incoming connections on port 80

This guide covers [Parallels Desktop](https://www.parallels.com/products/desktop/)
on macOS. The same principles apply to other hypervisors (UTM, VMware Fusion, VirtualBox) —
only the IP addresses and network adapter names differ.

## Prerequisites

- Parallels Desktop with a Windows VM
- RobotStudio installed in the VM with a virtual controller set up
  (see [Single Robot Setup](robot_setup_manual.md))
- Parallels networking set to **Shared Network** (the default)

## Automated setup (Parallels Pro/Business)

Two pixi tasks handle setup and verification separately, since a virtual controller
restart (and possibly a Windows reboot) is needed in between.

**Step 1 — install configuration:**

```bash
pixi run vm-setup
```

This validates your macOS host IP against `config/vcconf.xml`, installs the
whitelist file on the VM, and creates the Windows Firewall rule.

If you have multiple VMs, the script lists them and lets you pick one.
You can also skip the prompt with `VM=<name> pixi run vm-setup`.

**Step 2 — restart the virtual controller** in RobotStudio.

**Step 3 — verify connectivity:**

```bash
pixi run vm-verify
```

This detects the VM's IP, tests the RWS connection, and prints the `base_url`
to use in Python.

!!! warning
    Enabling remote RWS access exposes the entire host filesystem to RWS, not just
    the virtual controller files. Only whitelist trusted IPs.

## Manual setup

For other hypervisors, or if `prlctl` is unavailable, follow these steps.

### 1. Find the IP addresses

Parallels Shared Network uses the `10.211.55.0/24` subnet:

| Machine | IP | How to verify |
|---|---|---|
| macOS host | `10.211.55.2` (fixed) | `ifconfig vnic0` in Terminal |
| Windows VM | `10.211.55.x` (DHCP) | `ipconfig` in Command Prompt — look for the **Parallels** adapter |

Note the Windows VM IP — you'll need it for your Python `base_url`.

### 2. Configure RobotStudio to accept remote connections

RobotStudio's virtual controller blocks all non-localhost RWS connections by default.
To allow your macOS host to connect, create a whitelist file.

In the **Windows VM**, copy `config/vcconf.xml` from this repository to:

```
C:\Users\<username>\AppData\Roaming\ABB Industrial IT\Robotics IT\RobVC\vcconf.xml
```

!!! note
    The `RobVC` directory may not exist — create it if needed.

The repo is accessible inside Windows via Parallels shared folders at
`\\Mac\Home\<path-to-repo>\config\vcconf.xml`. You can also run the install
script directly from a Windows terminal:

```powershell
powershell -ExecutionPolicy Bypass -File "\\Mac\Home\<path-to-repo>\config\install_vcconf.ps1"
```

This copies `vcconf.xml` and creates the firewall rule (step 3) in one go.

The shipped `vcconf.xml` whitelists `10.211.55.2` (the default macOS host IP).
Edit it if your network uses a different subnet.

**Restart the virtual controller** in RobotStudio after installing.

### 3. Allow port 80 through Windows Firewall

!!! note
    `install_vcconf.ps1` handles this automatically. Only needed if setting up manually.

Open **Windows Defender Firewall with Advanced Security** and create an inbound rule:

1. **New Inbound Rule** → **Port** → **TCP 80**
2. **Allow the connection**
3. Scope: restrict **Remote IP** to `10.211.55.0/24` for security
4. Name it something recognizable, e.g. `RobotStudio RWS`

### 4. Restart the virtual controller

Restart the virtual controller in RobotStudio. A Windows reboot may also be
needed for the firewall rule to take effect.

### 5. Verify the connection

```bash
pixi run vm-verify
```

Or manually from macOS Terminal:

```bash
# Replace 10.211.55.x with your Windows VM IP
curl -u "Default User:robotics" http://10.211.55.x/rw/system
```

A successful response returns XML with controller information. If the connection
times out, double-check the firewall rule and `vcconf.xml`.

## Connect from Python

Use the Windows VM IP as `base_url`:

```python
import abb_motion_program_exec as abb

# Replace with your VM's IP address
client = abb.MotionProgramExecClient(base_url="http://10.211.55.x:80")
```

!!! tip
    To avoid hardcoding the IP, set an environment variable:

    ```bash
    export ABB_ROBOT_URL="http://10.211.55.4:80"
    ```

    ```python
    import os
    client = abb.MotionProgramExecClient(base_url=os.environ["ABB_ROBOT_URL"])
    ```

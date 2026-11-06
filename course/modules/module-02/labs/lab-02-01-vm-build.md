# Lab 2.1/2.2 — Build and Snapshot Both Analysis VMs

**Safety acknowledgment (restate before starting):** *"I will only perform these exercises in an isolated lab I own or am explicitly authorized to use, and I will not take any technique taught here outside that lab without separate written authorization."* See `../../../LAB_SAFETY.md` in full.

**Covers:** Lessons 2.1 (Building an Isolated VM Lab) and 2.2 (Windows and Linux Malware-Analysis VM Builds).

## Objective
Build a Host-Only-networked Windows VM and Linux VM, verify isolation at the OS level, harden the Windows VM for analysis use, and establish the `clean-base-install` snapshot for both.

## Required tools
- VirtualBox 7.x (or VMware Workstation/Fusion Player).
- A Windows 10/11 evaluation ISO (Microsoft evaluation center) and a current Ubuntu or Kali LTS ISO.

## Environment setup
- Host machine with VT-x/AMD-V enabled in firmware, 16 GB+ RAM recommended, 100+ GB free disk.

## Exercise instructions

1. In VirtualBox: File → Tools → Network Manager → Host-only Networks → Create. Confirm it creates a network (e.g. `vboxnet0`) in a private RFC1918 range (e.g. `192.168.56.0/24`) with DHCP enabled.
2. Create VM `malware-analysis-win`: 4+ GB RAM, 2+ cores, 60+ GB dynamic disk. **Before first boot**, set Settings → Network → Adapter 1 → Attached to: **Host-only Adapter**, select the network from step 1.
3. Install Windows from the evaluation ISO using a local/offline account (no Microsoft account sign-in).
4. Isolation check (run inside the guest):
   ```
   ipconfig          # confirm address is in the Host-Only range, no default gateway reachable
   ping 8.8.8.8       # MUST time out / 100% loss
   ```
   If the ping succeeds, stop and fix the adapter setting before continuing.
5. Harden the Windows VM for analysis use: disable Defender real-time protection, disable SmartScreen, pause/disable Windows Update (see Lesson 2.2 Practical Demonstration for exact commands/UI paths).
6. Install VirtualBox Guest Additions. Set Shared Clipboard and Drag'n'Drop to **Disabled** in VM Settings → General → Advanced.
7. Shut the VM down cleanly. Take a snapshot named `clean-base-install`.
8. Repeat steps 2–7 for a Linux VM named `malware-analysis-linux` (Ubuntu or Kali LTS, 4 GB RAM, 40 GB disk, Host-Only adapter, same isolation check, guest utilities via `apt install open-vm-tools`, same clipboard/drag-and-drop disable, same `clean-base-install` snapshot).

## Expected observations
- Both VMs show an address in the Host-Only range and fail to reach `8.8.8.8`.
- Windows VM: `Get-MpPreference | Select DisableRealtimeMonitoring` returns `True`.
- Both VMs have a named `clean-base-install` snapshot visible in the VirtualBox Snapshots pane.

## Validation steps
- Instructor/peer confirms (via screenshot or screen share): the Host-Only network's IP range, both VMs' `ipconfig`/`ip addr` output, both failed pings to `8.8.8.8`, and both snapshot names.

## Troubleshooting
- **Ping to 8.8.8.8 succeeds:** adapter is still on NAT/Bridged, or a second NAT-attached adapter exists — check all adapters in VM Settings → Network, not just Adapter 1.
- **`apt update` hangs on the Linux VM:** expected on Host-Only-only networking. Temporarily switch to NAT for package installs only, then switch back to Host-only and re-run the isolation check before any lab.
- **VM won't boot after enabling Host-only before OS install:** some installers need network access to fetch updates during setup; if the installer hangs, temporarily use NAT *only* for the OS install itself, then switch to Host-only before the isolation check and before installing any analysis tooling.

## Cleanup/reset
None — `clean-base-install` snapshot is the deliverable this lab produces, not something to revert away. Keep both VMs for Lesson 2.3's lab.

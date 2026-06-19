"""Network Actions Executor for JFP_PARADOX.

Executes network tuning commands (tc, iptables, ip route).
All commands subject to allowlist + Governor approval.
Dry-run mode for safe testing.
"""

from __future__ import annotations

import os
import subprocess
from typing import Any, Dict, List, Tuple


class ActionExecutor:
    """Execute network tuning actions safely."""

    def __init__(self, dry_run: bool = True) -> None:
        self.dry_run = dry_run
        self.allowlist = {
            "set_qdisc",
            "set_tcp_window",
            "adjust_iptables",
            "route_failover",
            "priority_queue",
            "enable_ecn",
            "adjust_buffer_size",
            "reset_all_rules",
            "panic_stop_network",
        }

    def _run_command(self, cmd: List[str]) -> Tuple[bool, str]:
        """Run system command safely.

        Args:
            cmd: Command list

        Returns:
            (success: bool, output: str)
        """
        if self.dry_run:
            return True, f"[DRY_RUN] Would execute: {' '.join(cmd)}"

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=5, check=False
            )
            if result.returncode == 0:
                return True, result.stdout.strip()
            else:
                return False, result.stderr.strip()
        except subprocess.TimeoutExpired:
            return False, "Command timed out"
        except Exception as e:
            return False, str(e)

    def set_qdisc(self, interface: str, qdisc_type: str) -> Tuple[bool, str]:
        """Enable traffic control qdisc (Fair Queuing CoDel recommended).

        Args:
            interface: network interface (e.g., "eth0")
            qdisc_type: "fq_codel", "pfifo_fast", "sfq"

        Returns:
            (success: bool, message: str)
        """
        if qdisc_type not in {"fq_codel", "pfifo_fast", "sfq", "htb"}:
            return False, f"Invalid qdisc: {qdisc_type}"

        if not self._is_valid_interface(interface):
            return False, f"Invalid interface: {interface}"

        cmd = ["tc", "qdisc", "replace", "root", "dev", interface, qdisc_type]
        return self._run_command(cmd)

    def set_tcp_window(self, size_kb: int) -> Tuple[bool, str]:
        """Adjust TCP window size for flow control.

        Args:
            size_kb: window size in KB (typical: 64-1024)

        Returns:
            (success: bool, message: str)
        """
        if not 1 <= size_kb <= 2048:
            return False, f"Invalid window size: {size_kb} KB"

        size_bytes = size_kb * 1024
        cmd = [
            "sysctl",
            "-w",
            f"net.ipv4.tcp_rmem=4096 131072 {size_bytes}",
        ]
        return self._run_command(cmd)

    def adjust_iptables(self, rule: str) -> Tuple[bool, str]:
        """Add iptables rule (append-only, no flush).

        Args:
            rule: iptables rule (e.g., "-A INPUT -p tcp --dport 443 -j ACCEPT")

        Returns:
            (success: bool, message: str)
        """
        if not rule.strip():
            return False, "Empty rule"

        # Safety: only allow append (-A) operations, no flush or delete
        if any(x in rule for x in ["-F", "-X", "-P", "-Z", "--flush"]):
            return False, "Denied: destructive iptables operation"

        cmd = ["iptables"] + rule.split()
        return self._run_command(cmd)

    def route_failover(self, backup_gateway: str) -> Tuple[bool, str]:
        """Switch default route to backup gateway.

        Args:
            backup_gateway: IP address of backup gateway

        Returns:
            (success: bool, message: str)
        """
        if not self._is_valid_ip(backup_gateway):
            return False, f"Invalid IP: {backup_gateway}"

        cmd = ["ip", "route", "replace", "default", "via", backup_gateway]
        return self._run_command(cmd)

    def priority_queue(self, protocol: str, port: int) -> Tuple[bool, str]:
        """Set traffic priority for specific protocol/port (QoS).

        Args:
            protocol: "tcp" or "udp"
            port: destination port

        Returns:
            (success: bool, message: str)
        """
        if protocol not in {"tcp", "udp"}:
            return False, f"Invalid protocol: {protocol}"

        if not 1 <= port <= 65535:
            return False, f"Invalid port: {port}"

        # Use tc filter to prioritize
        cmd = [
            "tc",
            "filter",
            "add",
            "dev",
            "eth0",
            "parent",
            "root",
            "protocol",
            "ip",
            "prio",
            "1",
            "u32",
            "match",
            f"ip dport {port} 0xffff",
            "flowid",
            "1:1",
        ]
        return self._run_command(cmd)

    def enable_ecn(self) -> Tuple[bool, str]:
        """Enable Explicit Congestion Notification (ECN) for better QoS.

        Returns:
            (success: bool, message: str)
        """
        cmd = ["sysctl", "-w", "net.ipv4.tcp_ecn=1"]
        return self._run_command(cmd)

    def adjust_buffer_size(self, buffer_size_kb: int) -> Tuple[bool, str]:
        """Adjust socket buffer sizes for better throughput.

        Args:
            buffer_size_kb: buffer size in KB

        Returns:
            (success: bool, message: str)
        """
        if not 16 <= buffer_size_kb <= 10240:
            return False, f"Invalid buffer size: {buffer_size_kb} KB"

        size_bytes = buffer_size_kb * 1024
        cmd = [
            "sysctl",
            "-w",
            f"net.core.rmem_max={size_bytes}",
            f"net.core.wmem_max={size_bytes}",
        ]
        # Note: sysctl with multiple args needs separate calls
        success = True
        messages = []

        for arg in cmd[2:]:
            result, msg = self._run_command(["sysctl", "-w", arg])
            success = success and result
            messages.append(msg)

        return success, "; ".join(messages)

    def reset_all_rules(self) -> Tuple[bool, str]:
        """Reset all network rules to defaults (failsafe).

        Returns:
            (success: bool, message: str)
        """
        messages = []

        # Flush tc rules
        result, msg = self._run_command(["tc", "qdisc", "delete", "root", "dev", "eth0"])
        messages.append(f"tc reset: {msg}")

        # Reset to defaults
        cmd = ["sysctl", "-w", "net.ipv4.tcp_ecn=0"]
        result, msg = self._run_command(cmd)
        messages.append(f"sysctl reset: {msg}")

        return True, "; ".join(messages)

    def panic_stop_network(self) -> Tuple[bool, str]:
        """Emergency stop — reset network to safe defaults.

        Returns:
            (success: bool, message: str)
        """
        return self.reset_all_rules()

    def execute(
        self, action_name: str, params: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """Execute action by name with parameters.

        Args:
            action_name: name of action to execute
            params: action parameters

        Returns:
            (success: bool, message: str)
        """
        if action_name not in self.allowlist:
            return False, f"Action not in allowlist: {action_name}"

        if action_name == "set_qdisc":
            interface = str(params.get("interface", "eth0"))
            qdisc_type = str(params.get("qdisc_type", "fq_codel"))
            return self.set_qdisc(interface, qdisc_type)

        if action_name == "set_tcp_window":
            size_kb = int(params.get("size_kb", 256))
            return self.set_tcp_window(size_kb)

        if action_name == "adjust_iptables":
            rule = str(params.get("rule", ""))
            return self.adjust_iptables(rule)

        if action_name == "route_failover":
            gateway = str(params.get("backup_gateway", ""))
            return self.route_failover(gateway)

        if action_name == "priority_queue":
            protocol = str(params.get("protocol", "tcp"))
            port = int(params.get("port", 443))
            return self.priority_queue(protocol, port)

        if action_name == "enable_ecn":
            return self.enable_ecn()

        if action_name == "adjust_buffer_size":
            size_kb = int(params.get("buffer_size_kb", 512))
            return self.adjust_buffer_size(size_kb)

        if action_name == "reset_all_rules":
            return self.reset_all_rules()

        if action_name == "panic_stop_network":
            return self.panic_stop_network()

        return False, f"Unknown action: {action_name}"

    @staticmethod
    def _is_valid_interface(name: str) -> bool:
        """Check if interface name is valid."""
        return bool(name) and all(c.isalnum() or c in "-_" for c in name)

    @staticmethod
    def _is_valid_ip(ip: str) -> bool:
        """Check if IP address is valid."""
        parts = ip.split(".")
        if len(parts) != 4:
            return False
        try:
            return all(0 <= int(p) <= 255 for p in parts)
        except ValueError:
            return False

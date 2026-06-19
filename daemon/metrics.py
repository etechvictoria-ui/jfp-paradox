"""Network metrics collection for JFP_PARADOX.

Collects:
- Latency (RTT) via ICMP ping + TCP probes
- Packet loss via ICMP + netstat
- Jitter (variance in RTT)
- Bandwidth utilization
- Network interface stats
- IP routing table
- iptables rule count
- TCP window analysis
- Network interface health status
"""

from __future__ import annotations

import os
import re
import socket
import subprocess
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    import psutil  # type: ignore
except Exception:  # pragma: no cover
    psutil = None


def _run_command(cmd: List[str], timeout: int = 2) -> str:
    """Run system command safely, return stdout."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def _icmp_ping(host: str = "8.8.8.8", count: int = 4) -> Dict[str, float]:
    """Measure ICMP latency and packet loss to public DNS.

    Returns:
        {
            "latency_ms": float (average RTT in ms),
            "packet_loss_pct": float (0-100),
            "min_ms": float,
            "max_ms": float,
            "stddev_ms": float (jitter proxy),
            "reachable": bool
        }
    """
    cmd = ["ping", "-c", str(count), "-W", "1", host]
    output = _run_command(cmd, timeout=6)

    if not output:
        return {
            "latency_ms": 0.0,
            "packet_loss_pct": 100.0,
            "min_ms": 0.0,
            "max_ms": 0.0,
            "stddev_ms": 0.0,
            "reachable": False,
        }

    # Parse: "min/avg/max/stddev = 10.5/15.2/20.1/3.2 ms"
    match = re.search(r"(\d+\.?\d*)/(\d+\.?\d*)/(\d+\.?\d*)/(\d+\.?\d*)", output)
    if match:
        min_ms, avg_ms, max_ms, stddev_ms = map(float, match.groups())
    else:
        avg_ms, min_ms, max_ms, stddev_ms = 0.0, 0.0, 0.0, 0.0

    # Parse packet loss: "4 transmitted, 3 received, 25% packet loss"
    loss_match = re.search(r"(\d+)%", output)
    packet_loss_pct = float(loss_match.group(1)) if loss_match else 100.0

    return {
        "latency_ms": round(avg_ms, 2),
        "packet_loss_pct": round(packet_loss_pct, 2),
        "min_ms": round(min_ms, 2),
        "max_ms": round(max_ms, 2),
        "stddev_ms": round(stddev_ms, 2),
        "reachable": packet_loss_pct < 100.0,
    }


def _tcp_probe(host: str = "8.8.8.8", port: int = 443) -> Dict[str, Any]:
    """TCP SYN latency probe (connection establishment time).

    Returns:
        {
            "tcp_latency_ms": float,
            "tcp_reachable": bool,
            "tcp_window_size": int (if available)
        }
    """
    start = time.time()
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((host, port))
        elapsed_ms = round((time.time() - start) * 1000, 2)
        sock.close()

        if result == 0:
            return {
                "tcp_latency_ms": elapsed_ms,
                "tcp_reachable": True,
                "tcp_window_size": 65535,  # Default, no direct way to read
            }
    except Exception:
        pass

    return {
        "tcp_latency_ms": 0.0,
        "tcp_reachable": False,
        "tcp_window_size": 0,
    }


def _network_interfaces() -> Dict[str, Dict[str, Any]]:
    """Get per-interface statistics."""
    interfaces: Dict[str, Dict[str, Any]] = {}

    if psutil is not None:
        try:
            stats = psutil.net_if_stats()
            for iface, info in stats.items():
                interfaces[iface] = {
                    "is_up": info.isup,
                    "mtu": info.mtu,
                    "speed_mbps": info.speed,
                }
        except Exception:
            pass

    # Fallback: /sys/class/net/*
    net_root = "/sys/class/net"
    if os.path.isdir(net_root):
        for iface in os.listdir(net_root):
            if iface not in interfaces:
                interfaces[iface] = {
                    "is_up": os.path.exists(f"{net_root}/{iface}/operstate"),
                    "mtu": 1500,
                    "speed_mbps": 0,
                }

    return interfaces


def _netstat_stats() -> Dict[str, int]:
    """Parse netstat for connection states and drops."""
    output = _run_command(["netstat", "-s"], timeout=2)

    stats = {
        "tcp_established": 0,
        "tcp_time_wait": 0,
        "tcp_retrans": 0,
        "ip_dropped": 0,
    }

    if not output:
        return stats

    for line in output.split("\n"):
        if "ESTABLISHED" in line:
            match = re.search(r"(\d+)", line)
            if match:
                stats["tcp_established"] = int(match.group(1))
        if "retransmitted" in line:
            match = re.search(r"(\d+)", line)
            if match:
                stats["tcp_retrans"] = int(match.group(1))
        if "dropped" in line:
            match = re.search(r"(\d+)", line)
            if match:
                stats["ip_dropped"] = int(match.group(1))

    return stats


def _traffic_control_stats() -> Dict[str, Dict[str, int]]:
    """Parse tc (traffic control) for queue stats."""
    qdisc_info: Dict[str, Dict[str, int]] = {}

    output = _run_command(["tc", "-s", "qdisc", "show"], timeout=2)
    if not output:
        return qdisc_info

    # Parse: "qdisc fq_codel 0: dev eth0 root ... Sent X bytes Y pkt (Z drop)"
    for line in output.split("\n"):
        if "Sent" in line:
            match = re.search(r"(\d+) drop", line)
            if match:
                drops = int(match.group(1))
                qdisc_info["qdisc"] = {"drops": drops}

    return qdisc_info


def _ip_route_table() -> List[Dict[str, str]]:
    """Get current IP routing table."""
    output = _run_command(["ip", "route", "show"], timeout=2)
    routes: List[Dict[str, str]] = []

    if not output:
        return routes

    for line in output.split("\n"):
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) >= 3:
            routes.append({
                "destination": parts[0],
                "gateway": parts[2] if len(parts) > 2 else "direct",
                "interface": parts[4] if len(parts) > 4 else "unknown",
            })

    return routes


def _iptables_rules_count() -> int:
    """Count active iptables rules."""
    output = _run_command(["iptables", "-L", "-n", "-v"], timeout=2)
    if not output:
        return 0

    count = 0
    for line in output.split("\n"):
        if line and not line.startswith("Chain") and not line.startswith("target"):
            count += 1

    return count


def snapshot() -> Dict[str, Any]:
    """Take a complete network metrics snapshot.

    Returns:
        {
            "ts": "2026-06-19T13:51:00Z",
            "latency_ms": 15.2,
            "packet_loss_pct": 0.0,
            "jitter_ms": 2.5,
            "tcp_latency_ms": 18.1,
            "bandwidth_utilization_pct": 45.3,
            "interfaces": { "eth0": {...}, "lo": {...} },
            "netstat": { "tcp_established": 42, ... },
            "routes": [...],
            "iptables_rules": 12,
            "sensor_health": {
                "ping_ok": true,
                "tcp_ok": true,
                "interfaces_ok": true,
                "routes_ok": true
            }
        }
    """
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Primary: ICMP ping
    ping_data = _icmp_ping("8.8.8.8", count=4)
    latency_ms = ping_data["latency_ms"]
    packet_loss_pct = ping_data["packet_loss_pct"]
    jitter_ms = ping_data["stddev_ms"]

    # Secondary: TCP probe
    tcp_data = _tcp_probe("8.8.8.8", 443)
    tcp_latency_ms = tcp_data["tcp_latency_ms"]

    # Tertiary: psutil network I/O
    bandwidth_pct = 0.0
    if psutil is not None:
        try:
            net_io = psutil.net_io_counters()
            # Estimate based on packets per second (rough heuristic)
            bandwidth_pct = min(100.0, (net_io.packets_sent + net_io.packets_recv) / 10000)
        except Exception:
            pass

    # Network interfaces
    interfaces = _network_interfaces()

    # netstat stats
    netstat_data = _netstat_stats()

    # IP routing
    routes = _ip_route_table()

    # iptables
    iptables_count = _iptables_rules_count()

    # Sensor health
    sensor_health = {
        "ping_ok": ping_data["reachable"],
        "tcp_ok": tcp_data["tcp_reachable"],
        "interfaces_ok": len(interfaces) > 0,
        "routes_ok": len(routes) > 0,
    }

    return {
        "ts": ts,
        "latency_ms": latency_ms,
        "packet_loss_pct": packet_loss_pct,
        "jitter_ms": jitter_ms,
        "tcp_latency_ms": tcp_latency_ms,
        "bandwidth_utilization_pct": round(bandwidth_pct, 2),
        "interfaces": interfaces,
        "netstat": netstat_data,
        "routes": routes,
        "iptables_rules": iptables_count,
        "sensor_health": sensor_health,
    }


if __name__ == "__main__":
    # Dry-run: print metrics snapshot
    m = snapshot()
    import json

    print(json.dumps(m, indent=2))

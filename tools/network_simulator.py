"""Network Simulator for JFP_PARADOX Testing.

Simulates network degradation scenarios for testing daemon responses.
Generates synthetic metrics with controllable degradation patterns.

Usage:
    python network_simulator.py --scenario latency_surge --duration 30
    python network_simulator.py --scenario packet_loss --duration 20 --severity high
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List


class NetworkSimulator:
    """Generate synthetic network metrics with degradation patterns."""

    def __init__(
        self,
        scenario: str = "normal",
        duration_s: int = 30,
        severity: str = "medium",
    ) -> None:
        self.scenario = scenario
        self.duration_s = duration_s
        self.severity = severity
        self.start_time = time.time()
        self.tick = 0

        # Severity multipliers
        self.severity_mult = {"low": 0.5, "medium": 1.0, "high": 2.0}.get(
            severity, 1.0
        )

    @staticmethod
    def _utc_now() -> str:
        """Get current UTC timestamp."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    @staticmethod
    def _mock_interfaces() -> Dict[str, Dict[str, Any]]:
        """Mock network interfaces."""
        return {
            "eth0": {"is_up": True, "mtu": 1500, "speed_mbps": 1000},
            "lo": {"is_up": True, "mtu": 65536, "speed_mbps": 0},
        }

    @staticmethod
    def _mock_routes() -> List[Dict[str, str]]:
        """Mock IP routing table."""
        return [
            {"destination": "default", "gateway": "192.168.1.1", "interface": "eth0"},
            {"destination": "10.0.0.0/8", "gateway": "direct", "interface": "eth0"},
        ]

    def snapshot(self) -> Dict[str, Any]:
        """Generate synthetic metrics snapshot based on scenario."""
        elapsed = time.time() - self.start_time
        progress = min(1.0, elapsed / self.duration_s)  # 0.0 to 1.0

        # Base metrics (healthy state)
        latency_ms = 20.0
        packet_loss_pct = 0.0
        jitter_ms = 2.0
        bandwidth_util = 30.0

        # Apply scenario
        if self.scenario == "normal":
            # Slight random variation
            latency_ms += random.gauss(0, 0.5)
            packet_loss_pct += random.gauss(0, 0.01)

        elif self.scenario == "latency_surge":
            # Gradual latency increase then recovery
            if progress < 0.5:
                surge = progress * 200 * self.severity_mult
            else:
                surge = (1.0 - progress) * 200 * self.severity_mult
            latency_ms = 20.0 + surge
            jitter_ms = 10.0 + surge * 0.1

        elif self.scenario == "packet_loss":
            # Packet loss spike
            if progress < 0.3:
                packet_loss_pct = 0.0
            elif progress < 0.7:
                loss_level = (progress - 0.3) / 0.4  # 0.0 to 1.0
                packet_loss_pct = loss_level * 5.0 * self.severity_mult
            else:
                packet_loss_pct = 0.0

        elif self.scenario == "jitter_spike":
            # Jitter increase
            jitter_ms = 2.0 + progress * 50.0 * self.severity_mult

        elif self.scenario == "bandwidth_saturation":
            # Bandwidth utilization increasing
            bandwidth_util = 30.0 + progress * 60.0 * self.severity_mult

        elif self.scenario == "multi_degradation":
            # Multiple metrics degrading simultaneously
            degradation = progress * self.severity_mult
            latency_ms = 20.0 + degradation * 150.0
            packet_loss_pct = degradation * 2.0
            jitter_ms = 2.0 + degradation * 30.0
            bandwidth_util = 30.0 + degradation * 50.0

        elif self.scenario == "oscillating":
            # Oscillating quality (WiFi-like)
            oscillation = math.sin(progress * math.pi * 4) * self.severity_mult
            latency_ms = 20.0 + oscillation * 100.0
            packet_loss_pct = max(0.0, oscillation * 2.0)
            jitter_ms = 2.0 + abs(oscillation) * 20.0

        # Clamp values to realistic ranges
        latency_ms = max(0.1, latency_ms)
        packet_loss_pct = max(0.0, min(100.0, packet_loss_pct))
        jitter_ms = max(0.0, jitter_ms)
        bandwidth_util = max(0.0, min(100.0, bandwidth_util))

        # Add small random jitter to all
        latency_ms += random.gauss(0, 1.0)
        packet_loss_pct += random.gauss(0, 0.05)
        jitter_ms += random.gauss(0, 0.5)
        bandwidth_util += random.gauss(0, 2.0)

        self.tick += 1

        return {
            "ts": self._utc_now(),
            "latency_ms": round(latency_ms, 2),
            "packet_loss_pct": round(packet_loss_pct, 2),
            "jitter_ms": round(jitter_ms, 2),
            "tcp_latency_ms": round(latency_ms + 5.0, 2),
            "bandwidth_utilization_pct": round(bandwidth_util, 2),
            "interfaces": self._mock_interfaces(),
            "netstat": {
                "tcp_established": int(20 + bandwidth_util),
                "tcp_time_wait": 5,
                "tcp_retrans": int(packet_loss_pct * 100),
                "ip_dropped": int(packet_loss_pct * 50),
            },
            "routes": self._mock_routes(),
            "iptables_rules": 12,
            "sensor_health": {
                "ping_ok": packet_loss_pct < 100.0,
                "tcp_ok": latency_ms < 1000.0,
                "interfaces_ok": True,
                "routes_ok": True,
            },
        }


def run_scenario(
    scenario: str, duration_s: int, severity: str, output_file: str | None = None
) -> None:
    """Run scenario and print/save metrics."""
    simulator = NetworkSimulator(scenario, duration_s, severity)

    print(f"🔄 Simulating: {scenario} ({duration_s}s, severity={severity})")
    print("─" * 60)

    snapshots = []
    start = time.time()

    while time.time() - start < duration_s:
        snapshot = simulator.snapshot()
        snapshots.append(snapshot)

        # Print progress
        print(
            f"[{simulator.tick:3d}] "
            f"latency={snapshot['latency_ms']:6.1f}ms "
            f"loss={snapshot['packet_loss_pct']:5.2f}% "
            f"jitter={snapshot['jitter_ms']:5.1f}ms"
        )

        time.sleep(1.0)

    print("─" * 60)
    print(f"✅ Simulation complete ({len(snapshots)} snapshots)")

    # Save to file if requested
    if output_file:
        with open(output_file, "w") as f:
            for snapshot in snapshots:
                f.write(json.dumps(snapshot) + "\n")
        print(f"📄 Saved to {output_file}")

    return snapshots


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Network Simulator for JFP_PARADOX testing"
    )
    parser.add_argument(
        "--scenario",
        choices=[
            "normal",
            "latency_surge",
            "packet_loss",
            "jitter_spike",
            "bandwidth_saturation",
            "multi_degradation",
            "oscillating",
        ],
        default="normal",
        help="Degradation scenario",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=30,
        help="Simulation duration in seconds",
    )
    parser.add_argument(
        "--severity",
        choices=["low", "medium", "high"],
        default="medium",
        help="Severity multiplier",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Save metrics to JSONL file",
    )

    args = parser.parse_args()

    try:
        run_scenario(
            scenario=args.scenario,
            duration_s=args.duration,
            severity=args.severity,
            output_file=args.output,
        )
    except KeyboardInterrupt:
        print("\n⏹️ Interrupted")
        sys.exit(0)


if __name__ == "__main__":
    main()

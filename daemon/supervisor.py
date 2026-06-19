"""Network Supervisor — Adaptive optimization for JFP_PARADOX.

Monitors network trend and recommends tuning actions (L1/L2/L3).
All recommendations must still pass GovernorConstitution approval.

Deque window: 8-second sliding (600 samples @ 1s tick rate).
"""

from __future__ import annotations

from collections import deque
from datetime import datetime
from typing import Any, Deque, Dict, Optional, Tuple


class Supervisor:
    """Adaptive but deterministic network optimizer."""

    def __init__(self) -> None:
        # 8-second window @ 1s sampling = 600 deque slots
        self.window: Deque[Dict[str, Any]] = deque(maxlen=600)
        self.enabled = True
        self.warn_threshold_latency_increasing = 10.0  # ms/sec
        self.warn_threshold_loss_increasing = 0.5  # %/sec
        self.warn_threshold_jitter_increasing = 5.0  # ms/sec

    @staticmethod
    def _parse_ts(ts: str) -> datetime:
        """Parse ISO8601 timestamp."""
        return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")

    def update(self, metrics_obj: Dict[str, Any]) -> None:
        """Add new metrics snapshot to window."""
        self.window.append(metrics_obj)

    def _latency_trend(self, seconds: int = 8) -> float:
        """Calculate latency delta per second over window.

        Returns:
            float: ms/second (positive = increasing latency = bad)
        """
        if len(self.window) < 2:
            return 0.0

        newest = self.window[-1]
        newest_ts = newest.get("ts")
        if not isinstance(newest_ts, str):
            return 0.0

        t2 = self._parse_ts(newest_ts)
        m2 = float(newest.get("latency_ms", 0.0))

        for old in reversed(self.window):
            old_ts = old.get("ts")
            if not isinstance(old_ts, str):
                continue
            t1 = self._parse_ts(old_ts)
            dt = (t2 - t1).total_seconds()
            if dt <= 0:
                continue
            if dt >= seconds:
                m1 = float(old.get("latency_ms", 0.0))
                trend = (m2 - m1) / dt
                return round(trend, 3)

        return 0.0

    def _packet_loss_trend(self, seconds: int = 8) -> float:
        """Calculate packet loss delta per second.

        Returns:
            float: %/second (positive = increasing loss = bad)
        """
        if len(self.window) < 2:
            return 0.0

        newest = self.window[-1]
        newest_ts = newest.get("ts")
        if not isinstance(newest_ts, str):
            return 0.0

        t2 = self._parse_ts(newest_ts)
        m2 = float(newest.get("packet_loss_pct", 0.0))

        for old in reversed(self.window):
            old_ts = old.get("ts")
            if not isinstance(old_ts, str):
                continue
            t1 = self._parse_ts(old_ts)
            dt = (t2 - t1).total_seconds()
            if dt <= 0:
                continue
            if dt >= seconds:
                m1 = float(old.get("packet_loss_pct", 0.0))
                trend = (m2 - m1) / dt
                return round(trend, 3)

        return 0.0

    def _jitter_trend(self, seconds: int = 8) -> float:
        """Calculate jitter delta per second.

        Returns:
            float: ms/second (positive = increasing jitter = bad)
        """
        if len(self.window) < 2:
            return 0.0

        newest = self.window[-1]
        newest_ts = newest.get("ts")
        if not isinstance(newest_ts, str):
            return 0.0

        t2 = self._parse_ts(newest_ts)
        m2 = float(newest.get("jitter_ms", 0.0))

        for old in reversed(self.window):
            old_ts = old.get("ts")
            if not isinstance(old_ts, str):
                continue
            t1 = self._parse_ts(old_ts)
            dt = (t2 - t1).total_seconds()
            if dt <= 0:
                continue
            if dt >= seconds:
                m1 = float(old.get("jitter_ms", 0.0))
                trend = (m2 - m1) / dt
                return round(trend, 3)

        return 0.0

    def recommend(self, metrics_obj: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Recommend network tuning action based on trends and current metrics.

        L3: Critical intervention needed (enable QoS, aggressive traffic shaping)
        L2: High intervention (enable TCP window scaling, adjust buffer)
        L1: Preventive monitoring (prepare failover route, set up alerting)

        Returns:
            {
                "level": "L1" | "L2" | "L3",
                "name": action name,
                "params": action parameters,
                "reason": string explaining recommendation
            }
            or None if no action needed
        """
        if not self.enabled:
            return None

        latency = float(metrics_obj.get("latency_ms", 0.0))
        packet_loss = float(metrics_obj.get("packet_loss_pct", 0.0))
        jitter = float(metrics_obj.get("jitter_ms", 0.0))
        bandwidth = float(metrics_obj.get("bandwidth_utilization_pct", 0.0))

        latency_trend = self._latency_trend(seconds=8)
        loss_trend = self._packet_loss_trend(seconds=8)
        jitter_trend = self._jitter_trend(seconds=8)

        # L3: Critical — multiple bad metrics or severe trends
        if (
            latency > 300.0
            or packet_loss > 3.0
            or jitter > 80.0
            or bandwidth > 90.0
        ):
            return {
                "level": "L3",
                "name": "set_qdisc",
                "params": {"interface": "eth0", "qdisc_type": "fq_codel"},
                "reason": f"critical_state latency={latency}ms loss={packet_loss}%",
            }

        # L2: High — one bad metric or increasing trends
        if latency > 200.0 or packet_loss > 1.5 or jitter > 50.0:
            return {
                "level": "L2",
                "name": "set_tcp_window",
                "params": {"size_kb": 256},
                "reason": f"high_degradation latency={latency}ms jitter={jitter}ms",
            }

        # L1: Preventive — watch for increasing trends
        if (
            latency_trend > self.warn_threshold_latency_increasing
            or loss_trend > self.warn_threshold_loss_increasing
            or jitter_trend > self.warn_threshold_jitter_increasing
        ):
            return {
                "level": "L1",
                "name": "prepare_failover",
                "params": {"backup_gateway": "192.168.1.2"},
                "reason": f"trend_worsening latency_trend={latency_trend}ms/s loss_trend={loss_trend}%/s",
            }

        return None

    def approve_action(
        self, action_name: str, metrics_obj: Dict[str, Any], params: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """Supervisor-level action approval.

        Checks:
        - Emergency stops always approved
        - Monitoring actions always approved
        - Aggressive actions (like failover) need strong signal

        Args:
            action_name: action being considered
            metrics_obj: current metrics
            params: action parameters

        Returns:
            (approved: bool, reason: str)
        """
        # Emergency always allowed
        if action_name in {"panic_stop_network", "reset_all_rules"}:
            return True, "allow_emergency"

        latency = float(metrics_obj.get("latency_ms", 0.0))
        packet_loss = float(metrics_obj.get("packet_loss_pct", 0.0))
        bandwidth = float(metrics_obj.get("bandwidth_utilization_pct", 0.0))

        latency_trend = self._latency_trend(seconds=8)
        loss_trend = self._packet_loss_trend(seconds=8)

        # Failover only if things are REALLY bad
        if action_name == "route_failover":
            if packet_loss < 2.0 and latency < 250.0:
                return False, "deny_failover_metrics_not_bad_enough"
            return True, "allow_failover_critical"

        # QoS ok if degraded
        if action_name == "set_qdisc":
            if bandwidth < 80.0 and latency < 300.0:
                return False, "deny_qdisc_premature"
            return True, "allow_qdisc_needed"

        # TCP window ok if rising trend
        if action_name == "set_tcp_window":
            if latency_trend < 5.0 and loss_trend < 0.2:
                return False, "deny_tcp_window_stable"
            return True, "allow_tcp_window_trending"

        # Default approve
        return True, "allow_supervisor"

"""Network-based Governor Constitution for JFP_PARADOX.

Hard safety rules for autonomous network governance.
No action can bypass this layer.

Formula: g(s, h_{n+1}) > θ => tune(R)
"""

from __future__ import annotations

from typing import Any, Dict, Tuple


class GovernorConstitution:
    """Hard network safety rules. Cannot be bypassed by supervisor."""

    def __init__(self) -> None:
        # Network health thresholds
        self.latency_critical_ms = 500.0
        self.latency_high_ms = 200.0
        self.packet_loss_critical_pct = 5.0
        self.packet_loss_high_pct = 1.0
        self.jitter_critical_ms = 100.0
        self.jitter_high_ms = 30.0
        self.bandwidth_utilization_critical_pct = 95.0

    @staticmethod
    def _gradient(
        current: Dict[str, float], next_snap: Dict[str, float]
    ) -> float:
        """Calculate g(s, h_{n+1}) — network health gradient.

        Weighted sum of metric deltas:
        - Latency delta: +0.5 per ms (increasing latency = negative)
        - Packet loss delta: +2.0 per % (loss increasing = very negative)
        - Jitter delta: +0.3 per ms (jitter increasing = negative)

        Returns:
            float: gradient value (higher = worse trajectory)
        """
        latency_delta = next_snap.get("latency_ms", 0.0) - current.get(
            "latency_ms", 0.0
        )
        loss_delta = next_snap.get("packet_loss_pct", 0.0) - current.get(
            "packet_loss_pct", 0.0
        )
        jitter_delta = next_snap.get("jitter_ms", 0.0) - current.get(
            "jitter_ms", 0.0
        )

        # Weighted gradient (loss degradation is worst)
        gradient = (latency_delta * 0.5) + (loss_delta * 2.0) + (jitter_delta * 0.3)
        return round(gradient, 3)

    def evaluate(self, metrics_obj: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate network health and determine criticality.

        Returns:
            {
                "health_score": 0-100,  # 100 = healthy
                "critical": bool,        # True if action needed
                "reason": str,           # Why critical (or "healthy")
                "thresholds_breached": [...],
                "sensor_health": {
                    "latency_ok": bool,
                    "loss_ok": bool,
                    "jitter_ok": bool,
                    "bandwidth_ok": bool,
                    "interfaces_ok": bool,
                    "routes_ok": bool
                }
            }
        """
        latency = float(metrics_obj.get("latency_ms", 0.0))
        packet_loss = float(metrics_obj.get("packet_loss_pct", 0.0))
        jitter = float(metrics_obj.get("jitter_ms", 0.0))
        bandwidth = float(metrics_obj.get("bandwidth_utilization_pct", 0.0))

        sensor_health = metrics_obj.get("sensor_health", {})
        if not isinstance(sensor_health, dict):
            sensor_health = {}

        latency_ok = bool(sensor_health.get("ping_ok", False))
        loss_ok = bool(sensor_health.get("ping_ok", False))
        jitter_ok = bool(sensor_health.get("tcp_ok", False))
        interfaces_ok = bool(sensor_health.get("interfaces_ok", False))
        routes_ok = bool(sensor_health.get("routes_ok", False))

        # Sensor missing = critical
        if not all([latency_ok, loss_ok, jitter_ok, interfaces_ok, routes_ok]):
            return {
                "health_score": 0.0,
                "critical": True,
                "reason": "sensor_missing",
                "thresholds_breached": ["sensor_health"],
                "sensor_health": {
                    "latency_ok": latency_ok,
                    "loss_ok": loss_ok,
                    "jitter_ok": jitter_ok,
                    "bandwidth_ok": bandwidth < self.bandwidth_utilization_critical_pct,
                    "interfaces_ok": interfaces_ok,
                    "routes_ok": routes_ok,
                },
            }

        # Check thresholds
        breached = []
        health_score = 100.0

        if latency >= self.latency_critical_ms:
            breached.append("latency_critical")
            health_score -= 40.0
        elif latency >= self.latency_high_ms:
            breached.append("latency_high")
            health_score -= 20.0

        if packet_loss >= self.packet_loss_critical_pct:
            breached.append("packet_loss_critical")
            health_score -= 50.0
        elif packet_loss >= self.packet_loss_high_pct:
            breached.append("packet_loss_high")
            health_score -= 25.0

        if jitter >= self.jitter_critical_ms:
            breached.append("jitter_critical")
            health_score -= 30.0
        elif jitter >= self.jitter_high_ms:
            breached.append("jitter_high")
            health_score -= 15.0

        if bandwidth >= self.bandwidth_utilization_critical_pct:
            breached.append("bandwidth_critical")
            health_score -= 20.0

        health_score = max(0.0, min(100.0, health_score))
        is_critical = health_score < 50.0 or len(breached) >= 2

        reason = "healthy"
        if breached:
            reason = breached[0]
        if is_critical and "critical" in reason:
            reason = "critical_state"

        return {
            "health_score": round(health_score, 2),
            "critical": is_critical,
            "reason": reason,
            "thresholds_breached": breached,
            "sensor_health": {
                "latency_ok": latency_ok,
                "loss_ok": loss_ok,
                "jitter_ok": jitter_ok,
                "bandwidth_ok": bandwidth < self.bandwidth_utilization_critical_pct,
                "interfaces_ok": interfaces_ok,
                "routes_ok": routes_ok,
            },
        }

    def approve_action(
        self, action_name: str, metrics_obj: Dict[str, Any], params: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """Approve or deny a network tuning action.

        Hard constitutional rules:
        - Emergency stops always allowed
        - Most actions only allowed if network is degraded (health < 70)
        - Dangerous actions (route changes) require critical state

        Args:
            action_name: "set_qdisc", "set_tcp_window", "adjust_iptables", etc
            metrics_obj: Current metrics snapshot
            params: Action parameters (e.g., {"interface": "eth0", "qdisc": "fq_codel"})

        Returns:
            (approved: bool, reason: str)
        """
        eval_result = self.evaluate(metrics_obj)
        health = eval_result["health_score"]
        is_critical = eval_result["critical"]

        # Emergency stops always allowed
        if action_name in {
            "panic_stop_network",
            "reset_all_rules",
            "failsafe_revert",
        }:
            return True, "allow_emergency_action"

        # Monitoring-only actions always allowed
        if action_name in {"get_network_state", "analyze_traffic"}:
            return True, "allow_monitoring"

        # Policy: Most tuning actions only if degraded
        if action_name in {
            "set_qdisc",
            "set_tcp_window",
            "adjust_iptables",
            "priority_queue",
        }:
            if health > 70.0:
                return False, "deny_tuning_network_healthy"
            return True, "allow_tuning_degraded"

        # Policy: Route failover only if critical
        if action_name == "route_failover":
            if not is_critical:
                return False, "deny_failover_not_critical"
            return True, "allow_failover_critical"

        # Unknown action
        return False, f"deny_unknown_action_{action_name}"

"""Tests for Governor Constitution and Action Executor."""

import pytest
from daemon.governor import GovernorConstitution
from daemon.supervisor import Supervisor
from daemon.actions import ActionExecutor


class TestGovernorConstitution:
    """Test hard safety rules."""

    @pytest.fixture
    def governor(self):
        return GovernorConstitution()

    def test_normal_network_not_critical(self, governor):
        """Normal network metrics should not trigger critical state."""
        metrics = {
            "latency_ms": 20.0,
            "packet_loss_pct": 0.0,
            "jitter_ms": 2.0,
            "bandwidth_utilization_pct": 30.0,
            "sensor_health": {
                "ping_ok": True,
                "tcp_ok": True,
                "interfaces_ok": True,
                "routes_ok": True,
            }
        }

        result = governor.evaluate(metrics)
        assert result["critical"] == False
        assert result["health_score"] == 100.0

    def test_high_latency_triggers_critical(self, governor):
        """High latency should trigger critical state."""
        metrics = {
            "latency_ms": 550.0,  # > 500ms critical
            "packet_loss_pct": 0.0,
            "jitter_ms": 2.0,
            "bandwidth_utilization_pct": 30.0,
            "sensor_health": {
                "ping_ok": True,
                "tcp_ok": True,
                "interfaces_ok": True,
                "routes_ok": True,
            }
        }

        result = governor.evaluate(metrics)
        assert result["critical"] == True
        assert result["health_score"] < 50.0

    def test_high_packet_loss_triggers_critical(self, governor):
        """High packet loss should degrade health."""
        metrics = {
            "latency_ms": 20.0,
            "packet_loss_pct": 2.0,  # > 1% high
            "jitter_ms": 2.0,
            "bandwidth_utilization_pct": 30.0,
            "sensor_health": {
                "ping_ok": True,
                "tcp_ok": True,
                "interfaces_ok": True,
                "routes_ok": True,
            }
        }

        result = governor.evaluate(metrics)
        assert "packet_loss_high" in result["thresholds_breached"]

    def test_multiple_threshold_breaches(self, governor):
        """Multiple threshold breaches should show all in list."""
        metrics = {
            "latency_ms": 350.0,  # Critical
            "packet_loss_pct": 2.0,  # High
            "jitter_ms": 40.0,  # High
            "bandwidth_utilization_pct": 30.0,
            "sensor_health": {
                "ping_ok": True,
                "tcp_ok": True,
                "interfaces_ok": True,
                "routes_ok": True,
            }
        }

        result = governor.evaluate(metrics)
        assert len(result["thresholds_breached"]) >= 2

    def test_sensor_missing_is_critical(self, governor):
        """Missing sensors should be critical."""
        metrics = {
            "latency_ms": 20.0,
            "packet_loss_pct": 0.0,
            "jitter_ms": 2.0,
            "bandwidth_utilization_pct": 30.0,
            "sensor_health": {
                "ping_ok": False,  # Sensor down
                "tcp_ok": True,
                "interfaces_ok": True,
                "routes_ok": True,
            }
        }

        result = governor.evaluate(metrics)
        assert result["critical"] == True
        assert "sensor_missing" in result["reason"]

    def test_approve_action_when_degraded(self, governor):
        """Governor should approve tuning when network is degraded."""
        metrics = {
            "latency_ms": 350.0,  # Degraded
            "packet_loss_pct": 2.0,
            "jitter_ms": 40.0,
            "bandwidth_utilization_pct": 30.0,
            "sensor_health": {
                "ping_ok": True,
                "tcp_ok": True,
                "interfaces_ok": True,
                "routes_ok": True,
            }
        }

        approved, reason = governor.approve_action("set_qdisc", metrics, {})
        assert approved == True
        assert "allow" in reason.lower()

    def test_deny_action_when_healthy(self, governor):
        """Governor should deny tuning when network is healthy."""
        metrics = {
            "latency_ms": 20.0,  # Healthy
            "packet_loss_pct": 0.0,
            "jitter_ms": 2.0,
            "bandwidth_utilization_pct": 30.0,
            "sensor_health": {
                "ping_ok": True,
                "tcp_ok": True,
                "interfaces_ok": True,
                "routes_ok": True,
            }
        }

        approved, reason = governor.approve_action("set_qdisc", metrics, {})
        assert approved == False


class TestSupervisor:
    """Test trend analysis and recommendations."""

    @pytest.fixture
    def supervisor(self):
        return Supervisor()

    def test_supervisor_recommends_on_degradation(self, supervisor):
        """Supervisor should recommend L1/L2/L3 based on metrics."""
        metrics = {
            "ts": "2026-06-19T14:42:00Z",
            "latency_ms": 350.0,  # Critical
            "packet_loss_pct": 2.0,
            "jitter_ms": 40.0,
            "bandwidth_utilization_pct": 30.0,
            "sensor_health": {
                "ping_ok": True,
                "tcp_ok": True,
                "interfaces_ok": True,
                "routes_ok": True,
            }
        }

        supervisor.update(metrics)
        rec = supervisor.recommend(metrics)

        assert rec is not None
        assert rec["level"] in ["L1", "L2", "L3"]
        assert "name" in rec
        assert "reason" in rec

    def test_supervisor_no_recommend_when_healthy(self, supervisor):
        """Supervisor should not recommend when network is healthy."""
        metrics = {
            "ts": "2026-06-19T14:42:00Z",
            "latency_ms": 20.0,
            "packet_loss_pct": 0.0,
            "jitter_ms": 2.0,
            "bandwidth_utilization_pct": 30.0,
            "sensor_health": {
                "ping_ok": True,
                "tcp_ok": True,
                "interfaces_ok": True,
                "routes_ok": True,
            }
        }

        supervisor.update(metrics)
        rec = supervisor.recommend(metrics)

        # Should not recommend for healthy network
        if rec:
            assert rec["level"] == "L1"  # Only preventive


class TestActionExecutor:
    """Test network action execution."""

    @pytest.fixture
    def executor(self):
        return ActionExecutor(dry_run=True)

    def test_executor_dry_run_safe(self, executor):
        """Dry-run mode should not execute real commands."""
        success, output = executor.set_qdisc("eth0", "fq_codel")
        assert success == True
        assert "[DRY_RUN]" in output or "Would execute" in output

    def test_set_qdisc_valid_interface(self, executor):
        """set_qdisc should accept valid interfaces."""
        success, output = executor.set_qdisc("eth0", "fq_codel")
        assert success == True

    def test_set_qdisc_invalid_interface(self, executor):
        """set_qdisc should reject invalid interface names."""
        success, output = executor.set_qdisc("invalid@interface!", "fq_codel")
        assert success == False

    def test_set_qdisc_invalid_type(self, executor):
        """set_qdisc should reject invalid qdisc types."""
        success, output = executor.set_qdisc("eth0", "invalid_qdisc")
        assert success == False

    def test_set_tcp_window(self, executor):
        """set_tcp_window should work."""
        success, output = executor.set_tcp_window(256)
        assert success == True

    def test_set_tcp_window_invalid_size(self, executor):
        """set_tcp_window should reject invalid sizes."""
        success, output = executor.set_tcp_window(10000)  # Too large
        assert success == False

    def test_route_failover_valid_ip(self, executor):
        """route_failover should accept valid IPs."""
        success, output = executor.route_failover("192.168.1.2")
        assert success == True

    def test_route_failover_invalid_ip(self, executor):
        """route_failover should reject invalid IPs."""
        success, output = executor.route_failover("invalid.ip.address")
        assert success == False

    def test_panic_stop(self, executor):
        """panic_stop_network should work."""
        success, output = executor.panic_stop_network()
        assert success == True

    def test_allowlist_enforcement(self, executor):
        """Only whitelisted actions should execute."""
        # Valid action
        success1, _ = executor.execute("set_qdisc", {"interface": "eth0", "qdisc_type": "fq_codel"})
        assert success1 == True

        # Invalid action
        success2, _ = executor.execute("malicious_action", {})
        assert success2 == False

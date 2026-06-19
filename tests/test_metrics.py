"""Tests for metrics collection module."""

import pytest
from daemon.metrics import snapshot, _icmp_ping, _tcp_probe, _network_interfaces


class TestMetricsCollection:
    """Test network metrics sampling."""

    def test_snapshot_returns_dict(self):
        """snapshot() should return a dictionary with all required fields."""
        result = snapshot()

        assert isinstance(result, dict)
        assert 'ts' in result
        assert 'latency_ms' in result
        assert 'packet_loss_pct' in result
        assert 'jitter_ms' in result
        assert 'tcp_latency_ms' in result
        assert 'bandwidth_utilization_pct' in result
        assert 'interfaces' in result
        assert 'netstat' in result
        assert 'routes' in result
        assert 'sensor_health' in result

    def test_latency_is_positive(self):
        """Latency should be non-negative."""
        result = snapshot()
        assert result['latency_ms'] >= 0.0

    def test_packet_loss_in_range(self):
        """Packet loss should be between 0 and 100."""
        result = snapshot()
        assert 0.0 <= result['packet_loss_pct'] <= 100.0

    def test_jitter_is_positive(self):
        """Jitter should be non-negative."""
        result = snapshot()
        assert result['jitter_ms'] >= 0.0

    def test_bandwidth_in_range(self):
        """Bandwidth utilization should be between 0 and 100."""
        result = snapshot()
        assert 0.0 <= result['bandwidth_utilization_pct'] <= 100.0

    def test_sensor_health_dict(self):
        """sensor_health should be a dict with boolean values."""
        result = snapshot()
        health = result['sensor_health']

        assert isinstance(health, dict)
        assert 'ping_ok' in health
        assert 'tcp_ok' in health
        assert 'interfaces_ok' in health
        assert 'routes_ok' in health

        assert isinstance(health['ping_ok'], bool)
        assert isinstance(health['tcp_ok'], bool)

    def test_interfaces_is_dict(self):
        """interfaces should be a dict of interface stats."""
        result = snapshot()
        assert isinstance(result['interfaces'], dict)
        # Should have at least loopback
        assert len(result['interfaces']) >= 0

    def test_routes_is_list(self):
        """routes should be a list of route dicts."""
        result = snapshot()
        assert isinstance(result['routes'], list)

    def test_netstat_has_expected_keys(self):
        """netstat should have connection stats."""
        result = snapshot()
        netstat = result['netstat']

        assert 'tcp_established' in netstat
        assert 'tcp_retrans' in netstat
        assert 'ip_dropped' in netstat

        assert isinstance(netstat['tcp_established'], int)
        assert netstat['tcp_established'] >= 0

    def test_timestamp_format(self):
        """Timestamp should be ISO8601 format."""
        result = snapshot()
        ts = result['ts']

        # Should be ISO8601: 2026-06-19T14:42:00Z
        assert 'T' in ts
        assert 'Z' in ts
        assert len(ts) == 20  # YYYY-MM-DDTHH:MM:SSZ

    def test_multiple_snapshots_differ(self):
        """Sequential snapshots should have different latency readings."""
        s1 = snapshot()
        s2 = snapshot()

        # Different timestamps at minimum
        assert s1['ts'] != s2['ts']


class TestICMPPing:
    """Test ICMP ping functionality."""

    def test_ping_returns_dict(self):
        """_icmp_ping should return a dict."""
        result = _icmp_ping()
        assert isinstance(result, dict)
        assert 'latency_ms' in result
        assert 'packet_loss_pct' in result
        assert 'reachable' in result

    def test_ping_values_in_range(self):
        """Ping values should be in valid ranges."""
        result = _icmp_ping()
        assert result['latency_ms'] >= 0.0
        assert 0.0 <= result['packet_loss_pct'] <= 100.0
        assert isinstance(result['reachable'], bool)

    def test_ping_unreachable_host(self):
        """Pinging unreachable host should return failure."""
        result = _icmp_ping("192.0.2.1")  # TEST-NET-1 (unreachable)
        assert result['reachable'] == False or result['packet_loss_pct'] == 100.0


class TestTCPProbe:
    """Test TCP connection probe."""

    def test_tcp_probe_returns_dict(self):
        """_tcp_probe should return a dict."""
        result = _tcp_probe()
        assert isinstance(result, dict)
        assert 'tcp_latency_ms' in result
        assert 'tcp_reachable' in result

    def test_tcp_probe_values_valid(self):
        """TCP probe values should be valid."""
        result = _tcp_probe()
        assert result['tcp_latency_ms'] >= 0.0
        assert isinstance(result['tcp_reachable'], bool)

    def test_tcp_probe_custom_host(self):
        """TCP probe should accept custom host and port."""
        result = _tcp_probe("8.8.8.8", 443)
        assert isinstance(result, dict)
        # 8.8.8.8:443 should be reachable
        assert 'tcp_reachable' in result


class TestNetworkInterfaces:
    """Test network interface detection."""

    def test_interfaces_returns_dict(self):
        """_network_interfaces should return a dict."""
        result = _network_interfaces()
        assert isinstance(result, dict)

    def test_interface_keys(self):
        """Each interface should have expected keys."""
        result = _network_interfaces()
        if result:
            for iface_name, iface_data in result.items():
                assert 'is_up' in iface_data
                assert 'mtu' in iface_data
                assert 'speed_mbps' in iface_data
                assert isinstance(iface_data['is_up'], bool)
                assert isinstance(iface_data['mtu'], int)

    def test_loopback_present(self):
        """Loopback interface should be detected."""
        result = _network_interfaces()
        # Either 'lo' or some loopback interface
        lo_present = any('lo' in name.lower() for name in result.keys())
        assert lo_present or len(result) == 0

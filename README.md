# JFP PARADOX

**Autonomous Network Governance System**

JFP PARADOX extends JFP_Console_POC's governance architecture to network domain. Instead of managing system resources (CPU/RAM/TEMP), it monitors network quality (latency, packet loss, jitter) and autonomously tunes network parameters to maintain health.

**Formula:** `g(s, h_{n+1}) > θ => tune(R)`

- `g(s, h_{n+1})` = Network health gradient (current vs next state)
- `θ` = Threshold (configurable)
- `tune(R)` = Network tuning action (QoS, traffic control, routing)

---

## Key Properties

| Property | How it is enforced |
|---|---|
| **Two-layer governance** | Every action passes Governor (hard constitutional rules) and Supervisor (adaptive optimizer). Both must approve. |
| **Autonomous tuning** | Daemon monitors network 24/7, detects degradation via 8-second trend window, recommends and executes tuning actions. |
| **Tamper-evident proof log** | SHA-256 hash-chain. Any modification to any historical record breaks the chain. Optional Ed25519 signing. |
| **Safe-mode dry run** | `JFP_DRY_RUN=1` (default) — No real system mutations. All actions logged but not executed. |
| **Streak-guard trigger** | Action only after 3 consecutive critical states (prevents false positives from transient spikes). |
| **Auth-gated write ops** | All tuning actions require operator token. Read-only RPC methods are public. |
| **Network metrics** | Latency (ICMP + TCP), Packet Loss, Jitter, Bandwidth, Interface Status, IP Routes, iptables rules. |

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  jfpd (daemon)                                          │
│                                                         │
│  ┌──────────┐     ┌───────────────┐   ┌─────────────┐  │
│  │ metrics  │────▶│  Governor     │──▶│   Action    │  │
│  │ sampler  │     │ Constitution  │   │   Executor  │  │
│  │ (1s tick)│     │  (hard rules) │   │ (allowlist) │  │
│  └──────────┘     └───────┬───────┘   └──────┬──────┘  │
│                           │                  │          │
│                   ┌───────▼───────┐          │          │
│                   │  Supervisor   │──────────┘          │
│                   │ (adaptive)    │                     │
│                   └───────────────┘                     │
│                                                         │
│  ┌────────────────────────────────────────┐            │
│  │  ProofLogger — SHA-256 chain + Ed25519 │            │
│  └────────────────────────────────────────┘            │
│                      │                                  │
│               Unix socket (AF_UNIX)                     │
│               JSON-RPC (8 methods)                      │
└──────────────────────┼──────────────────────────────────┘
                       │
         Tools for verification & testing
         - verify_chain.py (proof integrity)
         - network_simulator.py (degradation testing)
```

---

## Network Metrics

**Primary (ICMP Ping):**
- Latency (ms) — Round-trip time
- Packet loss (%) — % of packets dropped
- Jitter (ms) — Standard deviation of RTT

**Secondary (TCP):**
- TCP latency (ms) — Connection establishment time
- TCP window size — Flow control buffer

**System:**
- Bandwidth utilization (%)
- Network interfaces (up/down, MTU, speed)
- IP routing table
- iptables rule count
- TCP connection stats (established, retrans, dropped packets)

**Sensor health:**
- ping_ok — ICMP reachable
- tcp_ok — TCP port reachable
- interfaces_ok — Network interfaces detected
- routes_ok — IP routes available

---

## Network Tuning Actions

### L3 (Critical Intervention)
- **set_qdisc** — Enable Fair Queuing CoDel traffic control
  - Addresses: latency spike, packet loss, jitter
  - Command: `tc qdisc replace root dev eth0 fq_codel`

### L2 (High Priority)
- **set_tcp_window** — Adjust TCP window size for flow control
  - Addresses: latency, jitter, buffer issues
  - Command: `sysctl -w net.ipv4.tcp_rmem=...`

- **priority_queue** — QoS prioritization for specific traffic
  - Addresses: bandwidth pressure, application needs
  - Command: `tc filter add ... u32 match ...`

### L1 (Preventive)
- **prepare_failover** — Prepare backup route (not executed yet)
  - Addresses: routing resilience
  - Command: `ip route replace default via ...`

### Emergency
- **panic_stop_network** — Reset all rules to defaults
  - Clears all tc qdiscs, resets sysctl defaults
  - Command: `tc qdisc delete root dev eth0`

---

## Thresholds (GovernorConstitution)

```
latency_critical:      500ms
latency_high:          200ms
packet_loss_critical:  5%
packet_loss_high:      1%
jitter_critical:       100ms
jitter_high:           30ms
bandwidth_critical:    95%
```

---

## Quick Start

### Docker (Recommended)

```bash
# Build & run
docker-compose up -d

# Check daemon status
docker-compose logs jfpd

# Query via RPC (from another terminal)
curl --unix-socket /tmp/jfpd.sock -X POST \
  -H "Content-Type: application/json" \
  -d '{"id":"1","method":"health.ping","params":{},"session_token":"local-dev-token"}' \
  http://dummy/
```

### Local Development

```bash
# Terminal 1: Start daemon
export JFP_DRY_RUN=1
python daemon/jfpd.py

# Terminal 2: Query RPC in another shell
curl --unix-socket /run/jfpd.sock ...

# Terminal 3: Test with network simulator
python tools/network_simulator.py --scenario latency_surge --duration 30
```

---

## JSON-RPC Interface

All methods communicate via Unix socket (default: `/run/jfpd.sock`).

### Request Format
```json
{
  "id": "request-1",
  "method": "health.ping",
  "params": {},
  "session_token": "local-dev-token"
}
```

### Response Format
```json
{
  "id": "request-1",
  "ok": true,
  "result": { "state": "MONITORING", ... },
  "server_ts": "2026-06-19T13:51:00Z"
}
```

### Methods

| Method | Auth | Purpose |
|--------|------|---------|
| `health.ping` | ❌ | Check daemon health & state |
| `metrics.get_current` | ❌ | Get latest network metrics |
| `events.get_recent` | ❌ | Get recent proof log events |
| `policy.set_profile` | ✅ | Change network profile |
| `benchmark.unlock` | ✅ | Unlock benchmark mode (120s TTL) |
| `benchmark.start` | ✅ | Start network degradation benchmark |
| `benchmark.stop` | ✅ | Stop benchmark |
| `panic.stop` | ✅ | Emergency stop (reset all rules) |

---

## Proof Log

Every action is logged to `jfp_proof.jsonl` with:
- Timestamp (ISO8601 UTC)
- Event type (DAEMON_STARTED, TRIGGERED, INTERVENTION_EXECUTED, etc)
- SHA-256 hash chain (prev_hash + entry_hash)
- Optional Ed25519 signature (if `JFP_SIGNING_ENABLED=1`)

### Verify proof chain integrity
```bash
python tools/verify_chain.py /var/log/jfp/jfp_proof.jsonl
# Output: ✓ PASS: chain_valid records=1,234 signed=no
```

---

## Testing

### Run network simulator
```bash
# Simulate latency surge (5s, high severity)
python tools/network_simulator.py \
  --scenario latency_surge \
  --duration 5 \
  --severity high \
  --output metrics.jsonl

# Available scenarios:
#   - normal (baseline)
#   - latency_surge (RTT increases then recovers)
#   - packet_loss (packet loss spike)
#   - jitter_spike (variance increase)
#   - bandwidth_saturation (utilization increase)
#   - multi_degradation (all metrics degrade)
#   - oscillating (WiFi-like oscillation)
```

### Run unit tests
```bash
pytest tests/ -v
```

---

## Deployment

### Environment Variables

```bash
# Daemon settings
JFP_DRY_RUN=1                          # Safe mode (default: true)
JFP_SOCKET_PATH=/run/jfpd.sock        # RPC socket path
JFP_LOG_PATH=/var/log/jfp/jfp_proof.jsonl
JFP_OPERATOR_TOKEN=local-dev-token    # Auth token for write ops
JFP_SIGNING_ENABLED=0                 # Enable Ed25519 signing
JFP_SIGNING_KEY=/etc/jfp/signing.pem  # Ed25519 private key path
```

### systemd Service

```bash
# Install
sudo cp daemon/jfpd.service /etc/systemd/system/

# Start
sudo systemctl start jfpd
sudo systemctl enable jfpd

# Monitor
sudo journalctl -u jfpd -f
```

### Docker

```bash
docker build -t jfp-paradox:latest .
docker run -d \
  --name jfpd \
  -e JFP_DRY_RUN=1 \
  -v /var/log/jfp:/var/log/jfp \
  jfp-paradox:latest
```

---

## Architecture Decisions

### Why 2-layer governance?
Governor enforces hard safety (thresholds that must never be violated), while Supervisor adds adaptivity (trend analysis, recommendations). This prevents both overly aggressive tuning and missed opportunities.

### Why streak-trigger (3x)?
Network metrics naturally spike transiently (packet retransmit, WiFi hop). Requiring 3 consecutive critical states in 3 seconds ensures only persistent degradation triggers action.

### Why JSON-RPC over REST?
- Simpler parsing (no HTTP routing needed in daemon)
- Unix socket (no network stack overhead, local-only)
- Atomic request/response (easier proof logging)

### Why reuse from JFP_Console_POC?
- Proven 2-layer governance model
- SHA-256 proof logging architecture
- Streak-trigger state machine
- Only the **metrics** and **actions** domains differ

---

## Files

```
jfp-paradox/
├── daemon/
│   ├── jfpd.py              # Main daemon (RPC + state machine)
│   ├── metrics.py           # Network metrics collection
│   ├── governor.py          # Constitutional rules
│   ├── supervisor.py        # Trend analysis + recommendations
│   ├── actions.py           # Network tuning executor
│   ├── logger.py            # SHA-256 proof logging
│   └── jfpd.service         # systemd service file
│
├── tools/
│   ├── network_simulator.py # Network degradation simulator
│   └── verify_chain.py      # Proof chain verification
│
├── tests/
│   ├── test_governor.py
│   ├── test_supervisor.py
│   ├── test_metrics.py
│   ├── test_actions.py
│   ├── test_rpc_integration.py
│   └── conftest.py
│
├── shared/
│   └── protocol.json        # RPC interface spec
│
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md (this file)
```

---

## Performance

| Metric | Value |
|--------|-------|
| **Sampling rate** | 1 metric snapshot per second |
| **Decision latency** | < 100ms (metrics → governor → action) |
| **Memory usage** | ~50MB daemon + 10MB supervisor window |
| **Proof log size** | ~500 bytes per event |
| **Dry-run overhead** | < 1% (no actual system mutations) |

---

## Security Model

1. **Daemon runs as root** (needs `tc`, `iptables`, `ip route` access)
2. **RPC socket** is Unix domain (no network exposure)
3. **Write operations** require operator token
4. **Dry-run mode** by default (no mutations without explicit disable)
5. **Action allowlist** prevents arbitrary commands
6. **Proof log** is tamper-evident (hash-chain)

---

## Troubleshooting

### Daemon won't start
```bash
# Check if socket is still in use
sudo lsof -U | grep jfpd.sock
sudo rm -f /run/jfpd.sock

# Check permissions
sudo -l  # Should allow tc, iptables, ip
```

### Metrics not updating
```bash
# Check if ping/netstat/tc commands work
ping -c 1 8.8.8.8
netstat -s
tc -s qdisc show

# Check daemon logs
sudo journalctl -u jfpd -n 50
```

### Actions not executing
```bash
# Check if dry-run mode is enabled
echo $JFP_DRY_RUN  # Should be 0 to execute

# Check action logs
grep "INTERVENTION_EXECUTED" /var/log/jfp/jfp_proof.jsonl
```

---

## Roadmap (Future)

- [ ] WebSocket real-time metrics push (vs RPC polling)
- [ ] Multi-interface support (tune multiple NICs independently)
- [ ] ML-based anomaly detection (vs threshold-based)
- [ ] Integration with Prometheus/Grafana
- [ ] BGP route failover automation
- [ ] DDoS mitigation modes

---

## License

MIT License — See LICENSE for details

---

## References

- JFP_Console_POC: Autonomous System Governance
- formula: `g(s, h_{n+1}) > θ => tune(R)` (network health gradient)
- RFC 3168: Explicit Congestion Notification (ECN)
- Linux tc(8): Traffic Control

---

<div align="center">

**Autonomous Network Governance with Tamper-Evident Proof Logging**

</div>

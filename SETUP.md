# Setup Instructions

## Development Environment

### Prerequisites
- Python 3.10+
- Linux (for full functionality: tc, iptables, ip commands)

### Installation

```bash
# Clone repo
git clone https://github.com/etechvictoria-ui/jfp-paradox.git
cd jfp-paradox

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Testing

```bash
# Test metrics collection
python3 daemon/metrics.py

# Test governor rules
python3 -c "from daemon.governor import GovernorConstitution; print('✓ Governor OK')"

# Test supervisor
python3 -c "from daemon.supervisor import Supervisor; print('✓ Supervisor OK')"

# Test network simulator
python3 tools/network_simulator.py --scenario latency_surge --duration 5

# Start daemon (test mode)
export JFP_DRY_RUN=1
export JFP_LOG_PATH=/tmp/jfp_proof.jsonl
python3 daemon/jfpd.py
```

## Running Daemon

### Test Mode (Safe)
```bash
export JFP_DRY_RUN=1  # NO MUTATIONS
export JFP_LOG_PATH=/tmp/jfp_proof.jsonl
export JFP_SOCKET_PATH=@jfpd_test
python3 daemon/jfpd.py
```

### Production Mode (Requires Root)
```bash
sudo -E python3 daemon/jfpd.py
```

## RPC Interface

Query daemon via Unix socket:

```bash
python3 << 'HEREDOC'
import socket, json

def rpc(method, params={}):
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect("\0jfpd_test")  # abstract socket
    req = {"id":"1","method":method,"params":params,"session_token":"local-dev-token"}
    sock.send(json.dumps(req).encode())
    return json.loads(sock.recv(4096))

result = rpc("health.ping")
print(f"State: {result['result']['state']}")
HEREDOC
```

See README.md for complete API documentation.

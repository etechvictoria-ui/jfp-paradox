"""JFP_PARADOX Daemon — Autonomous Network Governance.

Main daemon process:
- Samples network metrics every 1 second
- Evaluates health via GovernorConstitution
- Recommends actions via Supervisor
- Executes tuning via ActionExecutor
- Logs all events to SHA-256 proof chain
- Exposes JSON-RPC interface via Unix socket

State machine: MONITORING → TRIGGERED → INTERVENTION → COOLDOWN → MONITORING
"""

from __future__ import annotations

import json
import os
import signal
import socket
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from actions import ActionExecutor
from governor import GovernorConstitution
from logger import ProofLogger
from metrics import snapshot
from supervisor import Supervisor


SOCKET_PATH = os.getenv("JFP_SOCKET_PATH", "/run/jfpd.sock")
LOG_PATH = os.getenv("JFP_LOG_PATH", "/var/log/jfp/jfp_proof.jsonl")
SEED_HASH = "0" * 64
DEFAULT_TOKEN = "local-dev-token"


class JFPDaemon:
    """Autonomous network governance daemon."""

    def __init__(self) -> None:
        self.state = "MONITORING"
        self.cooldown_until = 0.0
        self.monitor_interval_s = 1.0
        self.cooldown_s = 45.0
        self.operator_token = os.getenv("JFP_OPERATOR_TOKEN", DEFAULT_TOKEN)

        # Initialize components
        self.logger = ProofLogger(log_path=LOG_PATH, seed_hash=SEED_HASH)
        self.actions = ActionExecutor(dry_run=self._dry_run())
        self.governor = GovernorConstitution()
        self.supervisor = Supervisor()

        # State tracking
        self.trigger_streak = 0
        self.trigger_streak_required = 3
        self.benchmark_proc: Optional[Any] = None
        self.benchmark_unlock_until = 0.0
        self.benchmark_unlock_ttl_s = 120

        self._stop = False
        self._last_metrics: Dict[str, Any] = {}
        self._lock = threading.Lock()

        # Bootstrap
        self._bootstrap_runtime()

    def _dry_run(self) -> bool:
        """Check if running in dry-run (safe) mode."""
        return os.getenv("JFP_DRY_RUN", "1") != "0"

    def _bootstrap_runtime(self) -> None:
        """Initialize runtime directories and log initial event."""
        run_dir = os.path.dirname(SOCKET_PATH)
        if run_dir and not SOCKET_PATH.startswith("@"):
            os.makedirs(run_dir, exist_ok=True)
        if not SOCKET_PATH.startswith("@") and os.path.exists(SOCKET_PATH):
            os.remove(SOCKET_PATH)

        self._append_event("DAEMON_STARTED", {
            "state": self.state,
            "dry_run": self._dry_run(),
        })

    @staticmethod
    def _utc_now() -> str:
        """Get current UTC timestamp in ISO8601 format."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _append_event(self, event: str, payload: Dict[str, Any]) -> None:
        """Log event to proof chain."""
        record = {
            "ts": self._utc_now(),
            "event": event,
            "state": self.state,
            **payload,
        }
        self.logger.append(record)

    def _sample_metrics(self) -> Dict[str, Any]:
        """Take network metrics snapshot."""
        metrics = snapshot()
        self._last_metrics = metrics
        self.supervisor.update(metrics)
        return metrics

    def _check_threshold(self, metrics: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """Evaluate if network is in critical state.

        Returns:
            (is_critical: bool, eval_result: dict)
        """
        eval_result = self.governor.evaluate(metrics)
        is_critical = eval_result["critical"]
        return is_critical, eval_result

    def _on_triggered(self, metrics: Dict[str, Any], eval_result: Dict[str, Any]) -> None:
        """Handle TRIGGERED state — check streak, recommend action."""
        self.trigger_streak += 1

        if self.trigger_streak >= self.trigger_streak_required:
            # Streak complete — recommend action
            recommendation = self.supervisor.recommend(metrics)

            if recommendation:
                action_name = recommendation["name"]
                params = recommendation["params"]

                # Check Governor approval
                gov_approved, gov_reason = self.governor.approve_action(
                    action_name, metrics, params
                )

                if gov_approved:
                    # Check Supervisor approval
                    sup_approved, sup_reason = self.supervisor.approve_action(
                        action_name, metrics, params
                    )

                    if sup_approved:
                        # Execute action
                        success, output = self.actions.execute(action_name, params)

                        self._append_event("INTERVENTION_EXECUTED", {
                            "action": action_name,
                            "params": params,
                            "success": success,
                            "output": output,
                            "level": recommendation.get("level"),
                        })

                        if success:
                            self.state = "INTERVENTION"
                            self.cooldown_until = time.time() + self.cooldown_s
                    else:
                        self._append_event("SUPERVISOR_DENIED", {
                            "action": action_name,
                            "reason": sup_reason,
                        })
                else:
                    self._append_event("GOVERNOR_DENIED", {
                        "action": action_name,
                        "reason": gov_reason,
                    })

            self.trigger_streak = 0

    def _on_intervention(self, metrics: Dict[str, Any]) -> None:
        """Handle INTERVENTION state — wait for cooldown."""
        now = time.time()
        if now >= self.cooldown_until:
            self.state = "COOLDOWN"
            self._append_event("COOLDOWN_STARTED", {"duration_s": self.cooldown_s})

    def _on_cooldown(self, metrics: Dict[str, Any]) -> None:
        """Handle COOLDOWN state — return to monitoring after dwell."""
        now = time.time()
        if now >= self.cooldown_until:
            self.state = "MONITORING"
            self.trigger_streak = 0
            self._append_event("COOLDOWN_COMPLETE", {"resumed": "MONITORING"})

    def _tick(self) -> None:
        """Main daemon tick (1s interval)."""
        # Sample metrics
        metrics = self._sample_metrics()

        # Evaluate health
        is_critical, eval_result = self._check_threshold(metrics)

        # State machine
        if self.state == "MONITORING":
            if is_critical:
                self.state = "TRIGGERED"
                self.trigger_streak = 1
                self._append_event("TRIGGERED", eval_result)
            else:
                self.trigger_streak = 0

        elif self.state == "TRIGGERED":
            if not is_critical:
                self.state = "MONITORING"
                self.trigger_streak = 0
                self._append_event("RECOVERED", {"health_score": eval_result["health_score"]})
            else:
                self._on_triggered(metrics, eval_result)

        elif self.state == "INTERVENTION":
            self._on_intervention(metrics)

        elif self.state == "COOLDOWN":
            self._on_cooldown(metrics)

    def _rpc_health_ping(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """RPC: health.ping — Check daemon health."""
        return {
            "state": self.state,
            "trigger_streak": self.trigger_streak,
            "uptime_s": time.time(),
            "dry_run": self._dry_run(),
        }

    def _rpc_metrics_get_current(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """RPC: metrics.get_current — Get latest metrics snapshot."""
        return self._last_metrics

    def _rpc_events_get_recent(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """RPC: events.get_recent — Get recent proof log events."""
        limit = int(params.get("limit", 10))
        # Simple implementation: return empty for now (full impl would read log)
        return {"events": [], "limit": limit}

    def _rpc_policy_set_profile(self, params: Dict[str, Any], token: str) -> Dict[str, Any]:
        """RPC: policy.set_profile — Change network profile (requires auth)."""
        if token != self.operator_token:
            return {"error": "E_AUTH"}

        profile = str(params.get("profile", "balanced"))
        self._append_event("OPERATOR_PROFILE_SET", {"profile": profile})
        return {"profile": profile, "applied": True}

    def _rpc_benchmark_unlock(self, params: Dict[str, Any], token: str) -> Dict[str, Any]:
        """RPC: benchmark.unlock — Unlock benchmark mode (requires auth)."""
        if token != self.operator_token:
            return {"error": "E_AUTH"}

        self.benchmark_unlock_until = time.time() + self.benchmark_unlock_ttl_s
        return {
            "unlocked_until": self.benchmark_unlock_until,
            "ttl_s": self.benchmark_unlock_ttl_s,
        }

    def _rpc_benchmark_start(self, params: Dict[str, Any], token: str) -> Dict[str, Any]:
        """RPC: benchmark.start — Start network benchmark."""
        if token != self.operator_token:
            return {"error": "E_AUTH"}

        dry_run = bool(params.get("dry_run", True))
        self._append_event("BENCHMARK_STARTED", {"dry_run": dry_run})

        return {
            "started": True,
            "dry_run": dry_run,
            "benchmark_id": str(uuid.uuid4()),
        }

    def _rpc_benchmark_stop(self, params: Dict[str, Any], token: str) -> Dict[str, Any]:
        """RPC: benchmark.stop — Stop benchmark."""
        self._append_event("BENCHMARK_STOPPED", {})
        return {"stopped": True}

    def _rpc_panic_stop(self, params: Dict[str, Any], token: str) -> Dict[str, Any]:
        """RPC: panic.stop — Emergency stop (requires auth)."""
        if token != self.operator_token:
            return {"error": "E_AUTH"}

        success, output = self.actions.panic_stop_network()
        self._append_event("PANIC_STOP", {"success": success, "output": output})

        return {"stopped": True, "success": success}

    def _handle_rpc(self, data: str) -> str:
        """Handle JSON-RPC 2.0 request."""
        try:
            req = json.loads(data)
        except json.JSONDecodeError:
            return json.dumps({
                "id": None,
                "ok": False,
                "error": {"code": "E_PARSE", "message": "Invalid JSON"},
                "server_ts": self._utc_now(),
            })

        req_id = req.get("id")
        method = str(req.get("method", ""))
        params = req.get("params", {})
        token = str(req.get("session_token", ""))

        # Route to handler
        handler = None
        if method == "health.ping":
            handler = self._rpc_health_ping
        elif method == "metrics.get_current":
            handler = self._rpc_metrics_get_current
        elif method == "events.get_recent":
            handler = self._rpc_events_get_recent
        elif method == "policy.set_profile":
            handler = lambda p: self._rpc_policy_set_profile(p, token)
        elif method == "benchmark.unlock":
            handler = lambda p: self._rpc_benchmark_unlock(p, token)
        elif method == "benchmark.start":
            handler = lambda p: self._rpc_benchmark_start(p, token)
        elif method == "benchmark.stop":
            handler = lambda p: self._rpc_benchmark_stop(p, token)
        elif method == "panic.stop":
            handler = lambda p: self._rpc_panic_stop(p, token)
        else:
            return json.dumps({
                "id": req_id,
                "ok": False,
                "error": {"code": "E_INVALID_METHOD", "message": f"Unknown method: {method}"},
                "server_ts": self._utc_now(),
            })

        try:
            result = handler(params)
            if "error" in result:
                return json.dumps({
                    "id": req_id,
                    "ok": False,
                    "error": {"code": result["error"], "message": "Authorization denied"},
                    "server_ts": self._utc_now(),
                })

            return json.dumps({
                "id": req_id,
                "ok": True,
                "result": result,
                "server_ts": self._utc_now(),
            })
        except Exception as e:
            return json.dumps({
                "id": req_id,
                "ok": False,
                "error": {"code": "E_RUNTIME", "message": str(e)},
                "server_ts": self._utc_now(),
            })

    def _socket_listen(self) -> None:
        """Start JSON-RPC Unix socket server."""
        sock_addr = "\0" + SOCKET_PATH[1:] if SOCKET_PATH.startswith("@") else SOCKET_PATH

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.bind(sock_addr)
            sock.listen(5)

            while not self._stop:
                sock.settimeout(1.0)
                try:
                    client, _ = sock.accept()
                    data = client.recv(4096).decode("utf-8")
                    response = self._handle_rpc(data)
                    client.send(response.encode("utf-8"))
                    client.close()
                except socket.timeout:
                    continue
                except Exception as e:
                    print(f"Socket error: {e}")

        finally:
            sock.close()
            if not SOCKET_PATH.startswith("@") and os.path.exists(SOCKET_PATH):
                os.remove(SOCKET_PATH)

    def run(self) -> None:
        """Main daemon loop."""
        # Start RPC socket listener in background thread
        rpc_thread = threading.Thread(target=self._socket_listen, daemon=True)
        rpc_thread.start()

        # Main monitoring loop
        try:
            while not self._stop:
                self._tick()
                time.sleep(self.monitor_interval_s)
        except KeyboardInterrupt:
            pass
        finally:
            self._stop = True
            self._append_event("DAEMON_STOPPED", {})
            rpc_thread.join(timeout=2.0)

    def stop(self) -> None:
        """Stop daemon gracefully."""
        self._stop = True


def main() -> None:
    """Entry point."""
    daemon = JFPDaemon()

    def signal_handler(signum: int, frame: Any) -> None:
        daemon.stop()

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    daemon.run()


if __name__ == "__main__":
    main()

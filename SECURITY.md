# Security Policy

## Supported Versions

| Version | Supported |
|--------|-----------|
| 0.1.x  | ✅ Yes    |
| <0.1   | ❌ No     |

---

## Reporting a Vulnerability

If you find a security vulnerability, please report it responsibly.

**Do NOT** create a public GitHub issue. Instead:

1. Email: TODO - add your email
2. Wait for acknowledgment (24-48h)
3. Coordinate disclosure

---

## Security Model

### Threat Model

| Threat | Mitigation |
|--------|-------------|
| Unauthorized network changes | Token-gated operations |
| Arbitrary command execution | Actions allowlisted |
| False positive interventions | Two-layer governance (Governor + Supervisor) |
| Tampered audit log | SHA-256 hash chain |
| Accidental mutations | Dry-run mode (default) |

### Security Features

- **Dry-run mode**: Default enabled. No real network changes.
- **Token authentication**: Required for all write operations.
- **Actions allowlist**: Only predefined commands allowed.
- **Two-layer approval**: Both Governor and Supervisor must approve.
- **Streak guard**: 3 consecutive critical states required.
- **Cooldown**: 45s cooldown after intervention.

---

## Best Practices

1. Keep `JFP_DRY_RUN=1` in production
2. Use strong operator token
3. Monitor proof log for anomalies
4. Review actions before approval
5. Keep system updated

---

## Compliance

This project is provided as-is for educational and research purposes.

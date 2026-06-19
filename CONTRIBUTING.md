# Contributing to JFP PARADOX

## ⚠️ Project Status: In Development

This project is **actively under development**. APIs may change, features may be added/removed, and breaking changes can occur until the first stable release (v1.0.0).

---

## Development Roadmap

| Phase | Status | Description |
|-------|--------|------------|
| v0.1.0 | ✅ Done | Core metrics collection |
| v0.2.0 | ✅ Done | Governor + Supervisor |
| v0.3.0 | ✅ Done | Action executor |
| v0.4.0 | ✅ Done | Proof logger |
| v0.5.0 | ✅ Done | JSON-RPC interface |
| v0.6.0 | ✅ Done | Electron desktop app |
| v0.7.0 | ✅ Done | Test suite |
| v0.8.0 | 🔄 Next | Network simulator scenarios |
| v1.0.0 | 📋 Planned | First stable release |

---

## How to Contribute

### Reporting Issues

1. Check if issue already exists
2. Use issue template
3. Include: OS, Python version, error logs
4. For bugs: provide reproduction steps

### Suggesting Features

1. Open discussion first
2. Explain use case
3. Describe expected behavior
4. Consider security implications

### Pull Requests

1. Fork the repo
2. Create feature branch: `feature/your-feature`
3. Run tests: `pytest tests/ -v`
4. Ensure no lint errors
5. Update documentation
6. Submit PR with clear description

---

## Development Setup

```bash
# Clone
git clone https://github.com/etechvictoria-ui/jfp-paradox.git
cd jfp-paradox

# Virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install pytest pytest-asyncio

# Run tests
pytest tests/ -v

# Run daemon (dry-run mode)
python3 -m daemon.jfpd
```

---

## Code Style

- Python 3.12+ type hints required
- Follow PEP 8
- Use `pytest` for testing
- Add docstrings to public APIs

---

## Security Considerations

- All actions require token authentication
- Dry-run mode enabled by default
- Actions allowlisted (no arbitrary commands)
- Two-layer governance (Governor + Supervisor must both approve)

---

## License

MIT License - see LICENSE file.

# JFP_PARADOX v1.0 — Build & Release Instructions

## Building Standalone Executables

### Prerequisites

```bash
# Install Node.js 18+ (if not already installed)
# https://nodejs.org/

# Verify installation
node --version  # Should be v18+
npm --version   # Should be v9+
```

### Build for Your Platform

```bash
cd ui
npm install
npm run electron-build
```

### Output Files

After build completes, executables will be in `ui/dist/`:

**Windows:**
- `JFP PARADOX Setup 1.0.0.exe` — Installer (recommended)
- `JFP PARADOX 1.0.0.exe` — Portable version

**macOS:**
- `JFP PARADOX-1.0.0.dmg` — Disk image (drag to Applications)

**Linux:**
- `JFP PARADOX-1.0.0.AppImage` — Standalone executable
- `jfp-paradox_1.0.0_amd64.deb` — Debian package (Ubuntu/Debian)

### Installation

#### Windows
1. Download `JFP PARADOX Setup 1.0.0.exe`
2. Double-click to run installer
3. Follow prompts
4. Launch from Start Menu → "JFP PARADOX"

#### macOS
1. Download `JFP PARADOX-1.0.0.dmg`
2. Double-click to mount
3. Drag "JFP PARADOX" to Applications folder
4. Launch from Applications or Spotlight (Cmd+Space)

#### Linux (AppImage)
1. Download `JFP PARADOX-1.0.0.AppImage`
2. Make executable: `chmod +x JFP*.AppImage`
3. Double-click or run: `./JFP*.AppImage`

#### Linux (Debian/Ubuntu)
1. Download `jfp-paradox_1.0.0_amd64.deb`
2. Install: `sudo dpkg -i jfp-paradox_1.0.0_amd64.deb`
3. Launch: `jfp-paradox` or find in applications menu

---

## Development Build (Local Testing)

To test before building production executables:

```bash
cd ui
npm install
npm run dev
```

This will:
1. Start Vite dev server (http://localhost:5173)
2. Launch Electron window
3. Auto-start Python daemon
4. Enable hot-reload for changes

---

## Troubleshooting Build

### "electron not found"
```bash
npm install
```

### "vite not found"
```bash
npm install
```

### Build hangs/takes 5+ minutes
- First build is slower (downloading Electron binary)
- Subsequent builds are faster
- Typical build time: 2-3 minutes for full package

### File size too large
- Windows .exe: 180-200 MB (includes Chromium)
- macOS .dmg: 220 MB
- Linux AppImage: 190 MB
- This is expected (Electron bundles Chromium)

---

## Signing & Notarization (Optional, for Distribution)

For production distribution to many users:

### macOS Notarization
```bash
# Set environment variables
export APPLE_ID="your-apple-id@example.com"
export APPLE_PASSWORD="your-app-specific-password"
export APPLE_TEAM_ID="YOUR_TEAM_ID"

# Build will automatically notarize
npm run electron-build
```

### Windows Code Signing
```bash
# Requires certificate
export WIN_CERTIFICATE_FILE="path/to/cert.pfx"
export WIN_CERTIFICATE_PASSWORD="password"

npm run electron-build
```

---

## Post-Build Verification

After building, verify the app works:

### Windows
```cmd
.\dist\JFP PARADOX Setup 1.0.0.exe
# Or portable
.\dist\JFP PARADOX 1.0.0.exe
```

### macOS
```bash
open dist/JFP\ PARADOX-1.0.0.dmg
```

### Linux
```bash
./dist/JFP\ PARADOX-1.0.0.AppImage
```

**Expected behavior:**
1. Window launches with dark theme
2. Header shows "⚡ JFP PARADOX"
3. Status: "State: MONITORING | Health: 100/100"
4. No error messages in console

---

## Release Checklist

- [ ] Build successful (`npm run electron-build` completes)
- [ ] All platform binaries generated
- [ ] Tested app launch (at least one platform)
- [ ] Proof log created (~/.jfp_paradox/proof.jsonl)
- [ ] No error messages in daemon startup
- [ ] All 46 tests passing (`pytest tests/ -v`)
- [ ] Commit pushed to GitHub
- [ ] README updated with download links
- [ ] Release notes written

---

## Distribution

### GitHub Releases
1. Push code to GitHub
2. Create tag: `git tag v1.0.0`
3. Push tag: `git push origin v1.0.0`
4. Go to https://github.com/etechvictoria-ui/jfp-paradox/releases/new
5. Upload binary files from `ui/dist/`
6. Write release notes
7. Publish

### Direct Download
- Host binaries on your website
- Share direct download links
- Create simple landing page with install instructions

### Package Managers (Future)
- **Windows:** Chocolatey, WinGet
- **macOS:** Homebrew
- **Linux:** Snap, Flathub

---

## Performance Metrics

### App Startup Time
- First launch: 5-10 seconds (Python daemon startup)
- Subsequent launches: 2-3 seconds

### Memory Usage
- Electron app: ~200 MB
- Python daemon: ~50 MB
- Total: ~250 MB

### CPU Usage
- Idle: <1%
- Active monitoring: 2-5%
- Network degradation simulation: 10-15%

---

## Next Steps After Build

1. **Test on real system:** Verify it works on clean machine
2. **Gather feedback:** Ask users to test
3. **Iterate:** Fix bugs, improve UI
4. **Distribute:** Share download links
5. **Monitor:** Watch for issues, collect crash reports
6. **Update:** Release v1.0.1, v1.1, etc.

---

## Version Updates

To release new version (e.g., v1.0.1):

1. Update version in `ui/package.json`:
   ```json
   "version": "1.0.1"
   ```

2. Update in `ui/electron/main.js`:
   ```javascript
   // If you have version in code
   ```

3. Build again:
   ```bash
   npm run electron-build
   ```

4. Commit and push:
   ```bash
   git add .
   git commit -m "Release v1.0.1"
   git push
   git tag v1.0.1
   git push origin v1.0.1
   ```

---

## Support & Troubleshooting

### App won't start
- Check if Python is installed: `python3 --version`
- Check daemon logs: `cat ~/.jfp_paradox/jfpd.log`
- Try dev mode: `npm run dev`

### Network metrics not showing
- Ensure network connectivity
- Check if ICMP ping is allowed (firewall)
- Verify interfaces exist: `ip link show`

### Permission issues
- Daemon needs to read network files (not write)
- No sudo required for DRY_RUN=1 (default)
- Real network tuning (DRY_RUN=0) requires sudo

---

**Ready to build! Run `npm run electron-build` on your machine.**

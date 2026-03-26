# Parking Lot — Known Issues & Future Fixes

Items discovered during MSI installer sprint (2026-03-25). Not blocking, address when convenient.

## CI / Build

- [ ] **build-agent-msi.yml workflow broken** — YAML syntax or missing action reference. The MSI build runs manually on Windows, not in CI yet. Fix the workflow when ready to automate.
- [ ] **MSI uploads lost on API container rebuild** — Agent builds stored inside container filesystem (`/data/packages/`). Add a Docker volume mount in docker-compose.yml so uploads persist across rebuilds.

## Agent / Scanner

- [ ] **ETW ctypes backend not bundled** — `No module named 'providers._etw_ctypes'`. Agent falls back to polling telemetry. Add the ctypes ETW module to PyInstaller hidden imports if it should be bundled.
- [ ] **Linux commands called on Windows** — Scanner uses `pgrep`, `ps`, `lsof` which don't exist on Windows. Harmless (caught + skipped) but noisy in verbose logs. Add Windows equivalents or skip on `sys.platform == 'win32'`.
- [ ] **PowerShell version queries timeout** — Cursor and LM Studio scans call `powershell -Command (Get-Item ...).VersionInfo` which takes 10s+ on some machines. Consider async or caching.

## Server / API

- [ ] **ECE calibration test failure** — `test_ece_below_lenient_max`: ECE=0.31 > 0.20 threshold. Pre-existing. Fix calibration fixture corpus.
- [ ] **DETEC_API_URL must be set for MSI stamping** — The server defaults to `localhost:8000` which doesn't work for remote agents. Document in .env.example and SERVER.md. Consider deriving from request host header as fallback.

## Installer

- [ ] **Stale agent.env from previous installs** — If agent.env exists from a prior install, `_try_extract_installer_config()` skips trailer extraction. MSI upgrade scenario may leave old config. Consider checking if key is valid before skipping.
- [ ] **WiX Heat not available in WiX v6** — Using custom `harvest.ps1` script instead. Works but non-standard. Monitor if WiX adds official harvest support.
- [ ] **MajorUpgrade version handling** — All test MSIs used version 0.5.0 causing duplicate installs. Now fixed to 1.0.0 but bump version in DetecAgent.wxs for each real release.

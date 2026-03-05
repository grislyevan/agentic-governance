# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- Centralized collector configuration: JSON config file
  (`collector/config/collector.json`), environment variable overrides
  (`AGENTIC_GOV_*` prefix), and documented precedence
  (CLI > env > config file > code defaults).
- `collector/config_loader.py` — single module for loading and merging config
  from all sources.
- `collector/config/collector.example.json` — annotated example config with
  `config_version: 1`.
- Configuration section in `collector/README.md` covering config file location,
  env var table, and precedence rules.
- This `CHANGELOG.md` for tracking versioned, user-facing changes (complements
  `PROGRESS.md` which tracks ongoing development work).

### Changed

- `collector/main.py` now loads defaults from the config file and environment
  variables before applying CLI flags, rather than relying solely on hardcoded
  argparse defaults.

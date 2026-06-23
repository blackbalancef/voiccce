# Changelog

## 0.1.0 - Unreleased

### Changed
- `voiccce setup` now opens an interactive arrow-key + checkbox picker for choosing which agents to wire (Claude Code, Codex, pi) instead of the `[claude-code/codex/pi/both]` text prompt. `↑`/`↓` navigate, `space` toggles, `a` selects all, `enter` installs, `esc` cancels. The menu-bar prompt is now an arrow yes/no. Passing an explicit target (`claude-code`, `codex`, `pi`, or the legacy `both`) still works and skips the picker.

### Fixed
- pi integration now honors `PI_CODING_AGENT_DIR`, so alternate profiles such as `pi-personal` (which runs `PI_CODING_AGENT_DIR=$HOME/.pi-personal/agent pi`) get the extension installed into their own extensions directory instead of always `~/.pi/agent/extensions/`. Without this, voiccce stayed silent for pi-personal because pi never discovered the extension.



- Local SQLite event queue and daemon.
- Claude Code hook collector and personal settings installer.
- Session-aware notification state with deduplication, grouping, and stale/conflicting event suppression.
- English notification text with configurable templates.
- macOS `say`, desktop notification, terminal, and OpenAI TTS delivery.
- Local secret loading from environment variables, `~/.voiccce/.env`, or macOS Keychain.
- Optional macOS menu bar companion with stop-speaking, mute, daemon controls, and quick access to config/logs.
- Runtime voice controls: `stop-speaking`, `mute`, and `unmute`.
- `stop-speaking` now cancels pending OpenAI TTS playback and terminates voice playback process groups.

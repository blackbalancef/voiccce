# Changelog

## 0.1.0 - Unreleased

- Local SQLite event queue and daemon.
- Claude Code hook collector and personal settings installer.
- Session-aware notification state with deduplication, grouping, and stale/conflicting event suppression.
- English notification text with configurable templates.
- macOS `say`, desktop notification, terminal, and OpenAI TTS delivery.
- Local secret loading from environment variables, `~/.voiccce/.env`, or macOS Keychain.
- Optional macOS menu bar companion with stop-speaking, mute, daemon controls, and quick access to config/logs.
- Runtime voice controls: `stop-speaking`, `mute`, and `unmute`.
- `stop-speaking` now cancels pending OpenAI TTS playback and terminates voice playback process groups.

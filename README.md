# Agent Chime

Session-aware voice notifications for AI coding agents.

Agent Chime watches local agent lifecycle hooks and says short, useful notifications such as:

- "Claude Code in my-app needs attention: approve npm install."
- "Session my-app is fully complete."
- "Claude Code in api failed: tests did not pass."

The project is local-first: hooks write to a local SQLite queue, the daemon groups and deduplicates events, and delivery happens through macOS voice, desktop notifications, terminal logs, or optional OpenAI TTS.

## Features

- Claude Code hooks for `Stop`, `Notification`, `PermissionRequest`, `StopFailure`, and `SubagentStop`.
- Codex hooks for `Stop`, `PermissionRequest`, and `SubagentStop`.
- Deduplication, grouping, and stale/conflicting notification suppression.
- English notification text with configurable templates.
- macOS `say` by default, with optional OpenAI `gpt-4o-mini-tts`.
- Local config, SQLite queue, and logs under `~/.agent-chime`.
- API keys from environment variables, `~/.agent-chime/.env`, or macOS Keychain.

## Requirements

- macOS for voice playback and desktop notifications.
- Python 3.12+.
- `pipx` for the recommended install flow.
- Claude Code, if you want Claude hook integration.
- Codex CLI, if you want Codex hook integration.

## Install

Recommended install from GitHub:

```bash
git clone https://github.com/blackbalancef/agent-chime.git
cd agent-chime
git pull --ff-only
pipx install --force .
agent-chime install
```

To update an existing checkout later:

```bash
cd agent-chime
git pull --ff-only
pipx install --force .
agent-chime stop
agent-chime start
```

For the optional macOS menu bar companion:

```bash
pipx inject agent-chime pyobjc-framework-Cocoa
agent-chime menubar-start
```

After the package is published to PyPI, the shorter install path will be:

```bash
pipx install agent-chime
```

The legacy `agent-voice` command remains available as a compatibility alias.

## Quick Start

Initialize local config and database:

```bash
agent-chime install
```

Optional: add an OpenAI API key for cloud TTS and GPT summaries:

```bash
mkdir -p ~/.agent-chime
printf 'OPENAI_API_KEY=%s\n' 'replace-with-your-openai-key' > ~/.agent-chime/.env
chmod 600 ~/.agent-chime/.env
```

Optional: switch voice delivery from local macOS `say` to OpenAI TTS:

```bash
agent-chime config \
  --voice-backend openai_tts \
  --voice marin \
  --voice-speed 1.2 \
  --voice-model gpt-4o-mini-tts \
  --voice-format mp3 \
  --voice-api-key-env OPENAI_API_KEY
```

Install hooks for your agent, then start the daemon:

```bash
agent-chime install codex
# or: agent-chime install claude-code
agent-chime start
agent-chime status
agent-chime test
```

User-facing settings live in files under `~/.agent-chime`. Edit
`~/.agent-chime/config.toml` for message templates, voice backend, model,
speed, and speaking instructions. Edit `~/.agent-chime/.env` for API keys.

The built-in notification language is English:

```toml
[user]
language = "en"
```

Start or stop the background daemon:

```bash
agent-chime start
agent-chime status
agent-chime stop
```

Start or stop the menu bar companion:

```bash
agent-chime menubar-start
agent-chime menubar-status
agent-chime menubar-stop
```

## Claude Code

Install hooks into the default personal Claude Code config:

```bash
agent-chime install claude-code
agent-chime start
```

If you run Claude with a custom config directory, for example:

```bash
alias claude-personal='CLAUDE_CONFIG_DIR=$HOME/.claude-personal claude'
```

install hooks into that directory:

```bash
agent-chime install claude-code --claude-config-dir ~/.claude-personal
agent-chime start
claude-personal
```

You can also target a settings file directly:

```bash
agent-chime install claude-code --settings-path ~/.claude-personal/settings.json
```

The installer creates a backup next to the Claude `settings.json` file before changing hooks.

## Codex

Install hooks into the default personal Codex config:

```bash
agent-chime install codex
agent-chime start
```

If you run Codex with a custom `CODEX_HOME`, install hooks into that directory:

```bash
agent-chime install codex --codex-home ~/.codex-personal
agent-chime start
CODEX_HOME=~/.codex-personal codex
```

You can also target a hooks file directly:

```bash
agent-chime install codex --hooks-path ~/.codex-personal/hooks.json
```

The installer creates a backup next to `hooks.json` before changing hooks. If Codex app or `codex app-server` was already running, restart it so it reloads the new hooks file. Codex requires newly added command hooks to be reviewed and trusted; open `/hooks` in Codex and trust the Agent Chime hooks before normal runs.

## File-Based Configuration

`agent-chime install` creates `~/.agent-chime/config.toml`. Users can change
voice settings and message templates directly in this file:

```toml
[user]
language = "en"
timezone = "Europe/Belgrade"

[voice]
enabled = true
backend = "macos_say"
voice = "Alex"
rate = 185
speed = 1.0
model = "gpt-4o-mini-tts"
format = "mp3"
estimated_cost_per_minute_usd = 0.015
text_input_price_per_million_tokens_usd = 0.60
audio_output_price_per_million_tokens_usd = 12.00
audio_tokens_per_second = 20.833333
api_key_env = "OPENAI_API_KEY"
api_key_keychain_service = "agent-chime"
api_key_keychain_account = "openai"
instructions = "Speak naturally, calmly, and briefly. This is a short developer notification."
timeout_seconds = 15
```

Use these fields for common changes:

- `backend`: `macos_say` for local macOS voice, or `openai_tts` for OpenAI TTS.
- `voice`: macOS voice name for `macos_say`, or OpenAI TTS voice such as `marin`.
- `rate`: macOS `say` speaking rate.
- `speed`: OpenAI TTS speed, from `0.25` to `4.0`.
- `model`: OpenAI TTS model, for example `gpt-4o-mini-tts`.
- `format`: OpenAI audio format, such as `mp3`, `opus`, `aac`, `flac`, `wav`, or `pcm`.
- `estimated_cost_per_minute_usd`: legacy fallback estimate used to derive `audio_tokens_per_second` when that field is absent.
- `text_input_price_per_million_tokens_usd`: OpenAI TTS text input price used by local stats.
- `audio_output_price_per_million_tokens_usd`: OpenAI TTS generated audio price used by local stats.
- `audio_tokens_per_second`: estimated generated audio tokens per second. The default preserves the old `$0.015/min` audio estimate at `$12/1M` audio tokens.
- `instructions`: OpenAI TTS speaking style prompt.
- `api_key_env`: environment variable name read from `~/.agent-chime/.env` or the shell.

Restart the daemon after editing `config.toml`:

```bash
agent-chime stop
agent-chime start
```

## OpenAI TTS

The default backend is local macOS `say`. To use OpenAI TTS, put the key in
`~/.agent-chime/.env`:

```bash
mkdir -p ~/.agent-chime
printf 'OPENAI_API_KEY=%s\n' 'replace-with-your-openai-key' > ~/.agent-chime/.env
chmod 600 ~/.agent-chime/.env
```

Then configure the voice backend:

```bash
agent-chime config \
  --voice-backend openai_tts \
  --voice marin \
  --voice-speed 1.2 \
  --voice-model gpt-4o-mini-tts \
  --voice-format mp3 \
  --voice-api-key-env OPENAI_API_KEY \
  --voice-instructions "Speak naturally, calmly, and briefly."
```

Local audio spend is stored as an estimate because the speech endpoint returns
audio data, not per-request billing metadata. For OpenAI TTS the daemon now
stores the response `x-request-id`, a generated `X-Client-Request-Id`, estimated
text input tokens for `input` plus `instructions`, estimated audio output tokens
from generated duration, and separate input/output cost components. Install the
optional tokenizer for closer local text counts:

```bash
pipx inject agent-chime tiktoken
```

Without `tiktoken`, Agent Chime falls back to a conservative local token
heuristic. `audio_billed_cost_usd` is reserved for future Usage/Costs API
reconciliation; current dashboard totals still display `audio_cost_usd` as
estimated spend.

Restart the daemon and send a test notification:

```bash
agent-chime stop
agent-chime start
agent-chime test
```

You can store the key in macOS Keychain instead:

```bash
agent-chime secret set openai
agent-chime secret status openai
```

Current short notifications usually cost around `$0.0008-$0.0015` each on `gpt-4o-mini-tts`; exact cost depends mostly on generated audio duration.

## GPT Summaries Before Voice

By default, notifications use local fallback text. To make completed-session
voice notifications more natural, enable OpenAI summarization:

```toml
[summary]
enabled = true
provider = "openai"
model = "gpt-5.4-nano"
privacy_level = "full_last_message"
max_input_chars = 6000
max_words = 18
timeout_seconds = 5
text_input_price_per_million_tokens_usd = 0.20
cached_input_price_per_million_tokens_usd = 0.02
text_output_price_per_million_tokens_usd = 1.25
prompt = '''
Rewrite the final assistant update into one natural spoken notification.
Language: {language}
Project: {project}
Agent: {agent}
Status: {status}

Keep only what the user needs to know now. Write no more than {max_words} words and finish the sentence naturally.
Sound natural and varied, not like a status template. Do not mention internal paths, commands, or tests unless they are essential.
Return only the text to speak.

Final assistant update:
{message}
'''
```

`full_last_message` sends the final assistant message for completed sessions to
the summary model, then clears that transient text from the event row after the
daemon processes it. Use `metadata_only` to summarize the already-short local
notification text instead. `max_input_chars` caps the text sent to the cheap
summary model by keeping the beginning and end of the final message, so large
assistant reports do not become large summary requests. `max_words` tells the
model how short the spoken notification should be; the daemon does not hard-cut
the final spoken text, so the model can finish a coherent sentence. Summary
token spend is estimated from the model response `usage` fields and appears in
the CLI/menu bar dashboard as `Summaries`.

## Menu Bar

The optional macOS menu bar companion gives quick controls without opening a terminal:

- Dashboard: estimated audio spend, generated audio time/count, summary spend, and listened report count.
- `Stop Speaking`: stops the current `say` or `afplay` voice playback.
- `Mute 10 min` and `Mute 1 hour`: disables voice playback temporarily while keeping desktop/log notifications.
- `Unmute`: enables voice playback again.
- `Start Daemon` / `Stop Daemon`: controls the background processor.
- `Open Config` / `Open Daemon Log`: opens local files for debugging.

The same controls are available from CLI:

```bash
agent-chime stop-speaking
agent-chime mute --for 10m
agent-chime mute --for 1h
agent-chime unmute
```

## Custom Messages

Notification text is configurable in `~/.agent-chime/config.toml`.

Use `[messages.en]` to change message templates:

```toml
[messages.en]
attention_required = "Human input needed for {project}{reason_clause}."
permission_needed = "{agent} needs permission in {project}{reason_clause}."
completed = "Done: {project}."
completed_with_summary = "Done: {project}. Summary: {summary}."
failed = "{project} failed{reason_clause}."
```

Available placeholders:

- `{agent}`: agent name, for example `claude-code` or `codex`;
- `{project}`: project or session name;
- `{reason}`: short reason without punctuation;
- `{reason_clause}`: empty string or `: <reason>`;
- `{summary}`: final summary for completed sessions;
- `{count}` and `{items}`: grouped notification values.

For OpenAI TTS speaking style, edit `[voice].instructions`:

```toml
[voice]
instructions = "Speak naturally, calmly, and briefly."
```

## Useful Commands

Show status:

```bash
agent-chime status
```

List recent events:

```bash
agent-chime events --limit 20
```

Run one daemon pass without delivery:

```bash
agent-chime daemon --once --no-deliver
```

Enqueue a synthetic event:

```bash
agent-chime enqueue-test-event --type input_needed --project demo --session demo --ask "choose an approach"
```

## Privacy

Agent Chime runs locally. Claude and Codex hook payloads are normalized and sanitized before storage; the local SQLite database stores metadata and the short notification summary, not the full hook payload. If GPT summaries are enabled with `privacy_level = "full_last_message"`, the final assistant message for completed sessions is stored only as transient queue input and cleared after daemon processing.

When OpenAI TTS is enabled, only the final notification sentence is sent to the speech endpoint. When GPT summaries are enabled, the selected summary input is sent to the OpenAI Responses API before delivery. Without OpenAI TTS, voice delivery is local through macOS `say`.

## Development

```bash
python3 -m unittest discover -s tests
```

See `CONTRIBUTING.md` and `SECURITY.md` before opening changes that affect hooks, storage, delivery, or secrets.

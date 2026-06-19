# Agent Chime

Session-aware voice notifications for AI coding agents.

Agent Chime watches local agent lifecycle hooks (Claude Code and Codex) and speaks short, useful notifications such as:

- "Claude Code in my-app needs attention: approve npm install."
- "Session my-app is fully complete."
- "Claude Code in api failed: tests did not pass."

It is local-first: hooks write to a local SQLite queue, a background daemon groups and deduplicates events, and delivery happens through OpenAI TTS (recommended), the local macOS voice, desktop notifications, or terminal logs. Everything it stores lives under `~/.agent-chime` (config, queue, logs).

## Requirements

- macOS (for voice playback and desktop notifications).
- Python 3.12+ — check with `python3 --version`; if it's older, `brew install python@3.12`.
- `pipx` — install with `brew install pipx && pipx ensurepath`, then open a new terminal ([other ways to install pipx](https://pipx.pypa.io/stable/installation/)).
- Claude Code and/or Codex CLI — whichever agents you want notifications for.
- An OpenAI API key for the recommended voice ([get one here](https://platform.openai.com/api-keys)). You can skip it with `--local`, but the local macOS voice sounds noticeably worse.

## Quick start

Two steps: install the package, then run the one setup command.

```bash
# 1. Install the package
git clone https://github.com/blackbalancef/agent-chime.git
cd agent-chime
pipx install --force .
agent-chime --help                   # sanity check — if "command not found", run `pipx ensurepath`, open a new terminal, retry

# 2. Set up everything in one command
agent-chime setup
```

**Have an OpenAI API key?** (recommended — best voice) Run `agent-chime setup`. **No key?** Run `agent-chime setup --local` to use the built-in macOS voice (lower quality, works offline). Either way it is a single command.

`agent-chime setup` walks you through the whole thing interactively:

1. **Asks for your OpenAI API key** and saves it to the macOS Keychain.
2. **Turns on OpenAI TTS** (voice `marin` by default).
3. **Asks which agent to wire up** (`claude-code`, `codex`, or `both`) and installs the hooks.
4. **Starts the background daemon.**
5. **Sends a test notification** — you should hear it right away.

```text
$ agent-chime setup
OpenAI API key: ********
✓ OpenAI key saved to macOS Keychain
✓ Voice backend: openai_tts (voice: marin)
Wire hooks for? [claude-code/codex/both] (both): both
✓ Claude Code hooks → ~/.claude/settings.json
✓ Codex hooks → ~/.codex/hooks.json
✓ Daemon started (pid 4123)
✓ Test sent — you should hear it now.

Done. Edit ~/.agent-chime/config.toml to customize voice, messages, and summaries.
```

That's it. Agent Chime now speaks when your agent needs attention, finishes, or fails.

> Run it non-interactively by naming the agent up front, e.g. `agent-chime setup both` or `agent-chime setup claude-code`.
>
> **If your agent was already running** during setup, start a new session so it picks up the new hooks.
>
> **Codex only:** also open `/hooks` in Codex and **trust** the Agent Chime hooks (restart `codex app-server` if it was running). Details in [Codex](#codex).

### No OpenAI key? Use the local voice

```bash
agent-chime setup --local
```

`--local` skips the API key and uses the built-in macOS `say` voice. It works offline with zero setup, but the quality is noticeably lower than OpenAI TTS — handy to try things out. To switch to OpenAI later, store a key first, then change the backend:

```bash
agent-chime secret set openai                              # paste your key
agent-chime config --voice-backend openai_tts --voice marin
agent-chime stop && agent-chime start
```

### Updating

```bash
cd agent-chime
git pull --ff-only
pipx install --force .
agent-chime stop && agent-chime start
```

## Customize

Everything lives in one config file at `~/.agent-chime/config.toml`. Edit it, then restart the daemon:

```bash
agent-chime stop && agent-chime start
```

Common tweaks are also one-liners (each updates `config.toml` for you — no restart prompt, but restart to apply):

```bash
agent-chime config --voice cedar                 # pick a different OpenAI voice
agent-chime config --voice-backend macos_say     # switch to the local macOS voice (lower quality, no key)
agent-chime config --voice-backend openai_tts --voice marin   # switch back to OpenAI TTS (needs a stored key)
```

Switching to OpenAI TTS only takes effect once a key is stored (see [Managing the OpenAI key](#managing-the-openai-key)); without one, delivery silently falls back to the local macOS voice. See [Configuration](#configuration) for every field.

### Managing the OpenAI key

`agent-chime setup` stores the key in the macOS Keychain. Manage it with:

```bash
agent-chime secret status openai
agent-chime secret set openai        # paste a new key
agent-chime secret delete openai
agent-chime setup --reset-key        # re-prompt for a key even if one is already saved
```

If you'd rather not use the Keychain, Agent Chime also reads the key from the `OPENAI_API_KEY` shell variable or from `~/.agent-chime/.env` (resolved in that order: shell env → `.env` → Keychain). A `.env` template lives at [`.env.example`](.env.example).

### GPT summaries (optional)

To rewrite completed-session notifications into a more natural sentence, enable summaries in `~/.agent-chime/config.toml`:

```toml
[summary]
enabled = true
provider = "openai"
model = "gpt-5.4-nano"                 # any chat/Responses-capable model your OpenAI account can use
privacy_level = "full_last_message"   # or "metadata_only"
max_input_chars = 6000
max_words = 18
timeout_seconds = 5
```

`full_last_message` sends the final assistant message to the summary model, then clears that transient text after processing; `metadata_only` summarizes the already-short notification text instead. The block also accepts a multi-line `prompt = '''…'''` (placeholders `{language}`, `{project}`, `{agent}`, `{status}`, `{max_words}`, `{message}`) and three `*_price_per_million_tokens_usd` fields used for the local spend estimate. Restart the daemon after editing.

### Cost & accuracy

Short OpenAI TTS notifications usually cost about `$0.0008–$0.0015` each on `gpt-4o-mini-tts`; cost depends mostly on generated audio duration. Local spend is shown by `agent-chime status` and in the menu bar as an **estimate**, because the speech endpoint returns audio rather than billing data. For closer token counts, install the optional tokenizer:

```bash
pipx inject agent-chime tiktoken
```

## Claude Code

`agent-chime setup` (or `agent-chime install claude-code`) writes hooks into your personal Claude config (`~/.claude/settings.json`) and backs up the existing file first. Installed hooks: `Stop`, `Notification`, `PermissionRequest`, `StopFailure`, `SubagentStop`.

For a custom Claude config directory, pass it to either command:

```bash
agent-chime setup --claude-config-dir ~/.claude-personal
# or, hooks only:
agent-chime install claude-code --settings-path ~/.claude-personal/settings.json
```

## Codex

`agent-chime setup` (or `agent-chime install codex`) writes hooks into your personal Codex config and backs up `hooks.json` first. Installed hooks: `Stop`, `PermissionRequest`, `SubagentStop`.

For a custom `CODEX_HOME`:

```bash
agent-chime setup --codex-home ~/.codex-personal
CODEX_HOME=~/.codex-personal codex
```

**After installing Codex hooks:** restart the Codex app or `codex app-server` if it was already running so it reloads the new hooks file. Codex requires newly added command hooks to be reviewed and trusted — open `/hooks` in Codex and trust the Agent Chime hooks before normal runs.

## Configuration

The config file is `~/.agent-chime/config.toml`. Restart the daemon after editing (`agent-chime stop && agent-chime start`).

```toml
[user]
language = "en"            # built-in notification language
timezone = "Europe/Belgrade"

[voice]
enabled = true
backend = "macos_say"      # `agent-chime setup` switches this to "openai_tts"
voice = "Alex"             # macOS voice name; OpenAI voices look like "marin" or "cedar"
rate = 185                 # macOS say speaking rate
speed = 1.0                # OpenAI TTS speed, 0.25–4.0
model = "gpt-4o-mini-tts"  # OpenAI TTS model
format = "mp3"             # mp3, opus, aac, flac, wav, or pcm
api_key_env = "OPENAI_API_KEY"
api_key_keychain_service = "agent-chime"
api_key_keychain_account = "openai"
instructions = "Speak naturally, calmly, and briefly. This is a short developer notification."
timeout_seconds = 15
```

The remaining `[voice]` fields tune only the **local spend estimate** shown in `agent-chime status` and the menu bar:

- `estimated_cost_per_minute_usd` — legacy fallback used to derive `audio_tokens_per_second` when that field is absent.
- `text_input_price_per_million_tokens_usd` / `audio_output_price_per_million_tokens_usd` — OpenAI TTS prices used by local stats.
- `audio_tokens_per_second` — estimated generated audio tokens per second.

### Custom message templates

Change the spoken text with `[messages.en]`:

```toml
[messages.en]
attention_required = "Human input needed for {project}{reason_clause}."
permission_needed = "{agent} needs permission in {project}{reason_clause}."
completed = "Done: {project}."
completed_with_summary = "Done: {project}. Summary: {summary}."
failed = "{project} failed{reason_clause}."
```

Available placeholders: `{agent}`, `{project}`, `{reason}`, `{reason_clause}`, `{summary}`, `{count}`, `{items}`.

## Menu bar (optional)

A macOS menu bar companion gives quick controls without a terminal:

```bash
pipx inject agent-chime pyobjc-framework-Cocoa
agent-chime menubar-start
```

It shows estimated spend and generated-audio stats, and offers Stop Speaking, Mute 10 min / 1 hour, Unmute, Start/Stop Daemon, and Open Config / Daemon Log. The same controls are available from the CLI:

```bash
agent-chime stop-speaking
agent-chime mute --for 10m        # or 1h
agent-chime unmute
agent-chime menubar-stop
```

## Command reference

| Command | What it does |
| --- | --- |
| `agent-chime setup [claude-code\|codex\|both]` | **One-command setup:** OpenAI key → voice → hooks → daemon → test. Flags: `--local` (macOS say, no key), `--voice <name>`, `--reset-key`, `--no-test` |
| `agent-chime install [claude-code\|codex]` | Create config + database, and (with a target) wire agent hooks |
| `agent-chime start` / `stop` / `status` | Manage the background daemon |
| `agent-chime test` | Send a test notification |
| `agent-chime config …` | Show or change voice/language settings |
| `agent-chime secret set\|status\|delete openai` | Manage the API key in macOS Keychain |
| `agent-chime mute --for 10m` / `unmute` / `stop-speaking` | Control playback |
| `agent-chime menubar-start` / `menubar-stop` / `menubar-status` | Menu bar companion |
| `agent-chime events --limit 20` | List recent events |
| `agent-chime enqueue-test-event --type input_needed --project demo --session demo --ask "choose an approach"` | Enqueue a synthetic event |
| `agent-chime daemon --once --no-deliver` | Run one daemon pass without delivery |

The legacy `agent-voice` command is a compatibility alias for `agent-chime`.

## Privacy

Agent Chime runs locally. Claude and Codex hook payloads are normalized and sanitized before storage; the local SQLite database keeps metadata and the short notification summary, not the full hook payload. With GPT summaries and `privacy_level = "full_last_message"`, the final assistant message for completed sessions is stored only as transient queue input and cleared after the daemon processes it.

When OpenAI TTS is enabled, only the final notification sentence is sent to the speech endpoint. When summaries are enabled, the selected summary input is sent to the OpenAI Responses API before delivery. With the local macOS `say` backend, voice delivery is entirely on-device.

## Development

```bash
python3 -m unittest discover -s tests
```

See `CONTRIBUTING.md` and `SECURITY.md` before opening changes that affect hooks, storage, delivery, or secrets.

# Security

## Secrets

Never commit real API keys. Voiccce resolves the OpenAI key in this order:

1. the configured environment variable, `OPENAI_API_KEY` by default;
2. `~/.voiccce/.env`;
3. macOS Keychain.

Use `.env.example` as a template only.

## Data Handling

Agent hooks are processed locally. The SQLite database lives under `~/.voiccce` by default.

The Claude Code and Codex collectors store sanitized metadata and the short notification summary, not the complete hook payload. If GPT summaries are enabled with `privacy_level = "full_last_message"` (the default), the final assistant message for completed sessions is stored only as transient queue input and cleared after daemon processing. When OpenAI TTS is enabled, only the final notification sentence is sent to the OpenAI speech endpoint. When GPT summaries are enabled, the selected summary input is sent to the OpenAI Responses API before voice delivery. With `privacy_level = "metadata_only"`, only the already-short notification text is summarized.

## Summary pipeline log

When AI summaries are enabled, Voiccce writes a summary pipeline log to `~/.voiccce/summary.log` (rotated to `summary.log.1` past 5 MB). This file is created with owner-only permissions (`0600`). It records the full notification pipeline in **plaintext**: the assistant's last message, the prompt sent to the model, the model's raw and cleaned output, and the final spoken text. It is enabled by default; disable it with `voiccce config --summary-pipeline-log off`, and clear it (along with notification/session history) with `voiccce clear --history`.

## Reporting

If you find a vulnerability, please open a private security advisory on GitHub when available. If the repository does not have advisories enabled yet, contact the maintainers privately before publishing details.

# Contributing

Thanks for helping improve Agent Chime.

## Local Setup

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
python3 -m unittest discover -s tests
```

## Development Notes

- Keep the default path local-first and privacy-conscious.
- Do not add network calls to the hook collector. Delivery adapters may use the network only when explicitly configured.
- Do not commit API keys, generated databases, local logs, or files from `~/.agent-chime`.
- Add focused tests for behavior changes in collectors, queueing, session state, daemon processing, installer behavior, and delivery fallbacks.

## Pull Requests

Open a PR with:

- the user-facing behavior change;
- test coverage or a clear reason tests are not applicable;
- any privacy or security implications.

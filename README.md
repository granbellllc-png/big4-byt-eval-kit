# BIG4 BYT Evaluation Kit

Client-side evaluation kit for testing the **BIG4 BYT (Bring Your Token)** OpenAI-compatible endpoint (`https://104-207-84-209.sslip.io/v1/chat/completions`) with zero server-side persistence of provider API keys (**RAM-only**).

## Quickstart (2 minutes)

1. Copy `.env.example` to `.env` and set your keys:
   ```bash
   export BIG4_API_KEY="<your-big4-tenant-api-key>"
   export BYT_API_KEY="<your-openai-anthropic-openrouter-or-gemini-key>"
   export BIG4_MODEL="big4-byt-eval:openai/gpt-4o"
   ```
2. Run the 3-prompt smoke evaluation (verifies Ed25519 receipt offline, calls `/stats`, and writes `eval_report.json`):
   ```bash
   python3 francesco_smoke_eval.py
   ```

## Inline Hooks

| Hook | Behavior |
| :--- | :--- |
| *(default on `big4-byt-eval`)* | Runs `NAKED` first, VERITAS footer, then `BIG4` (`/both` + `/veritas-on`) |
| `/naked` | Runs your BYT baseline model only |
| `/big4` | Runs the verified Big4 pipeline only |
| `/both` | Runs `NAKED` first, then `BIG4` |
| `/veritas-on` / `/veritas-off` | Enables or disables the VERITAS footer + Epistemic Delta |
| `/inject-flaw` | Injects a controlled synthetic flaw before the `T=0` critic |
| `/stats` | Returns in-RAM session scorecard (`0` LLM tokens) |

See [SKILL.md](./SKILL.md) for Python/TypeScript SDK snippets, programmatic headers (`X-Big4-Eval-Mode`, `X-Big4-Veritas`), and offline Ed25519 receipt verification.

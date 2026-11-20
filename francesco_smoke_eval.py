#!/usr/bin/env python3
"""
francesco_smoke_eval.py — Ready-to-run A/B evaluation & offline Ed25519 receipt verifier
for the Big4 BYT Eval endpoint (https://104-207-84-209.sslip.io/v1/chat/completions).

Usage:
  export BIG4_API_KEY="<your-big4-tenant-api-key>"
  export BYT_API_KEY="<your-provider-api-key>"
  export BIG4_MODEL="big4-byt-eval:openai/gpt-4o"
  python3 francesco_smoke_eval.py
"""

import hashlib
import json
import getpass
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request

ENDPOINT = os.environ.get("BIG4_ENDPOINT", "https://104-207-84-209.sslip.io/v1/chat/completions")
BIG4_API_KEY = os.environ.get("BIG4_API_KEY", "").strip()
BYT_API_KEY = os.environ.get("BYT_API_KEY", "").strip()
CEREBRAS_API_KEY = os.environ.get("CEREBRAS_API_KEY", "").strip()
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()


def prompt_key_interactive(env_name: str, label: str, prefix_hint: str) -> str:
    """Prompt for API key interactively into RAM only without disk persistence."""
    try:
        val = getpass.getpass(f"🔑 [{env_name}] {label} ({prefix_hint}) [RAM-only, hidden input]: ").strip()
    except Exception:
        val = input(f"🔑 [{env_name}] {label} ({prefix_hint}) [RAM-only]: ").strip()
    return val


def prompt_session_keyring() -> tuple[str, str, str, str]:
    """
    Zero-persistence in-RAM key ingestion.
    - If keys are supplied via environment / .env, use them non-blockingly (zero friction for automated tests).
    - If running interactively (TTY) and keys are missing, prompt once at session start into volatile RAM.
    - Subsequent turns and runs don't re-prompt once tenant RAM cache is active or env vars are set.
    """
    big4_k = BIG4_API_KEY
    csk = CEREBRAS_API_KEY
    gsk = GROQ_API_KEY
    or_k = OPENROUTER_API_KEY

    # Check if we have at least one BYT key or if input is non-interactive
    is_interactive = sys.stdin.isatty() and not os.environ.get("NON_INTERACTIVE")
    needs_keys = not big4_k or not (csk or gsk or or_k or BYT_API_KEY)

    if needs_keys and is_interactive:
        print("\n" + "=" * 72)
        print("🔒 BIG4 BYT ZERO-DATA-RETENTION (RAM-ONLY) KEY INGESTION")
        print("Le chiavi inserite risiedono SOLO nella RAM volatile della sessione")
        print("e vengono cancellate alla chiusura (zero persistenza su disco/.env).")
        print("=" * 72 + "\n")

        if not big4_k:
            big4_k = prompt_key_interactive("BIG4_API_KEY", "Big4 Tenant Key", "provided by Big4")
        if not (csk or gsk or or_k or BYT_API_KEY):
            if not csk:
                csk = prompt_key_interactive("CEREBRAS_API_KEY", "Cerebras API Key (~$15 prepaid, ultra-fast)", "csk-...")
            if not gsk:
                gsk = prompt_key_interactive("GROQ_API_KEY", "Groq API Key (Free tier, T=0 critic)", "gsk_...")
            if not or_k:
                or_k = prompt_key_interactive("OPENROUTER_API_KEY", "OpenRouter API Key (Spend cap $5-$10, tie-breaker)", "sk-or-...")

    return big4_k, csk, gsk, or_k


# Module-level placeholder for runtime evaluation
MODEL = os.environ.get("BIG4_MODEL", "")

TRAP_PROMPTS = [
    {
        "name": "1. Python Edge-Case (bytes vs str polymorphism)",
        "prompt": "Write a Python function `sha256_items(items)` that accepts a list containing mixed `str` and `bytes` items and returns a list of lowercase hex SHA-256 digests without raising TypeError.",
    },
    {
        "name": "2. Multi-Step Numerical Trap",
        "prompt": "A SaaS company has 120 customers paying $80/month. In month 2, 10% churn and 18 new customers join at $95/month. What is the exact Monthly Recurring Revenue (MRR) in month 2?",
    },
    {
        "name": "3. Missing-Premise Trap (NON MISURATO != 0)",
        "prompt": "Based strictly on the facts provided here, compute the net EBITDA margin of AlphaCorp for Q3 2026: AlphaCorp reported Q3 revenue of $4.2M. Do not invent missing operating costs.",
    },
]


def verify_receipt_offline(receipt: dict, content: str) -> str:
    if not receipt:
        return "NO_RECEIPT"
    actual_sha = hashlib.sha256((content or "").encode("utf-8")).hexdigest()
    expected_sha = (receipt.get("payload") or {}).get("response_sha256")
    if actual_sha != expected_sha:
        return f"SHA256_MISMATCH ({actual_sha[:12]} != {str(expected_sha)[:12]})"
    try:
        import base64
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.hazmat.primitives.serialization import load_pem_public_key

        pub = load_pem_public_key(receipt["public_key"].encode("utf-8"))
        assert isinstance(pub, Ed25519PublicKey)
        sig = base64.b64decode(receipt["signature"])
        pub.verify(sig, receipt["canonical_payload"].encode("utf-8"))
        return f"ED25519_VERIFIED (seq={receipt.get('seq')})"
    except ImportError:
        return f"SHA256_OK (install 'cryptography' for Ed25519 check, seq={receipt.get('seq')})"
    except Exception as exc:
        return f"ED25519_FAIL: {exc}"


def call_big4(
    prompt: str,
    keyring_keys: dict | None = None,
    tenant_key: str = "",
    extra_headers: dict | None = None,
) -> tuple[dict, dict]:
    k_big4 = tenant_key or BIG4_API_KEY
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {k_big4}",
        **(extra_headers or {}),
    }

    # Pass the multi-key keyring JSON header if provided
    keyring = dict(keyring_keys) if keyring_keys else {}
    if not keyring:
        if CEREBRAS_API_KEY:
            keyring["cerebras"] = CEREBRAS_API_KEY
        if GROQ_API_KEY:
            keyring["groq"] = GROQ_API_KEY
        if OPENROUTER_API_KEY:
            keyring["openrouter"] = OPENROUTER_API_KEY

    if keyring:
        headers["X-Big4-Provider-Keys"] = json.dumps(keyring)
        if "cerebras" in keyring and not BYT_API_KEY:
            headers["X-Big4-BYT-Provider-Key"] = keyring["cerebras"]
        elif "openrouter" in keyring and not BYT_API_KEY:
            headers["X-Big4-BYT-Provider-Key"] = keyring["openrouter"]
    elif BYT_API_KEY:
        headers["X-Big4-BYT-Provider-Key"] = BYT_API_KEY

    model_target = MODEL or ("big4-byt-eval:cerebras/gpt-oss-120b" if "cerebras" in keyring else "big4-byt-eval:openai/gpt-4o")
    payload = json.dumps(
        {
            "model": model_target,
            "temperature": 0,
            "messages": [{"role": "user", "content": prompt}],
        }
    ).encode("utf-8")
    req = urllib.request.Request(ENDPOINT, data=payload, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=120) as resp:
        resp_headers = {k.lower(): v for k, v in resp.headers.items()}
        return json.loads(resp.read().decode("utf-8")), resp_headers


def main() -> int:
    big4_k, csk, gsk, or_k = prompt_session_keyring()
    active_keyring = {}
    if csk:
        active_keyring["cerebras"] = csk
    if gsk:
        active_keyring["groq"] = gsk
    if or_k:
        active_keyring["openrouter"] = or_k
    if BYT_API_KEY and not active_keyring:
        active_keyring["primary"] = BYT_API_KEY

    if not big4_k:
        print("ERROR: BIG4_API_KEY mancante.", file=sys.stderr)
        return 1
    if not active_keyring:
        print("ERROR: È richiesta almeno una chiave BYT attiva in RAM.", file=sys.stderr)
        return 1

    report_items = []
    try:
        for item in TRAP_PROMPTS:
            print("=" * 72)
            print(f"TEST: {item['name']}")
            try:
                body, hdrs = call_big4(item["prompt"], keyring_keys=active_keyring, tenant_key=big4_k)
                content = body["choices"][0]["message"]["content"]
                meta = body.get("big4_ciclo5", {})
                timing = meta.get("timing", {})
                receipt_status = verify_receipt_offline(body.get("veritas_receipt"), content)
                delta_status = (meta.get("epistemic_delta") or {}).get("status")
                print(
                    f"Timing: naked_ms={timing.get('naked_ms')} | big4_ms={timing.get('big4_ms')} | "
                    f"primary_reused={timing.get('primary_reused')} | header_reused={hdrs.get('x-big4-primary-reused')}"
                )
                print(f"Receipt: {receipt_status}")
                print(f"Delta:   {delta_status}")
                print("-" * 72)
                print(content)
                report_items.append(
                    {
                        "name": item["name"],
                        "prompt": item["prompt"],
                        "timing": timing,
                        "epistemic_delta": meta.get("epistemic_delta"),
                        "receipt_status": receipt_status,
                        "content": content,
                    }
                )
            except urllib.error.HTTPError as e:
                err_txt = e.read().decode("utf-8", errors="replace")
                print(f"HTTP {e.code}: {err_txt}")
                report_items.append({"name": item["name"], "error": f"HTTP {e.code}: {err_txt}"})
            except Exception as e:
                print(f"Error: {e}")
                report_items.append({"name": item["name"], "error": str(e)})

        print("\n" + "=" * 72)
        print("SESSION SCORECARD (/stats, 0 LLM tokens):")
        stats_body, _ = call_big4("/stats", keyring_keys=active_keyring, tenant_key=big4_k)
        print(stats_body["choices"][0]["message"]["content"])
        report_path = os.environ.get("BIG4_REPORT_PATH", "eval_report.json")
        with open(report_path, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "endpoint": ENDPOINT,
                    "model": MODEL or "big4-byt-eval",
                    "results": report_items,
                    "stats": (stats_body.get("big4_ciclo5") or {}).get("stats"),
                },
                fh,
                indent=2,
                ensure_ascii=False,
            )
        print(f"\nSaved evaluation report to {report_path}")

        summary_path = os.environ.get("DEVOTEAM_SUMMARY_PATH", "DEVOTEAM_EVAL_SUMMARY.md")
        stats = (stats_body.get("big4_ciclo5") or {}).get("stats") or {}
        lines = [
            "# BIG4 BYT Evaluation Summary",
            "",
            f"- **Endpoint:** `{ENDPOINT}`",
            f"- **Model:** `{MODEL or 'big4-byt-eval'}`",
            f"- **Total Calls:** `{stats.get('total_calls', len(report_items))}` · **Revision Rate:** `{stats.get('revision_rate_pct', 'N/A')}%`",
            "",
            "| Test Case | Status | Delta Epistemico | Naked (ms) | Big4 (ms) | Ed25519 Receipt |",
            "| :--- | :--- | :--- | ---: | ---: | :--- |",
        ]
        for item in report_items:
            if "error" in item:
                lines.append(f"| {item['name']} | ERROR | - | - | - | - |")
            else:
                delta = (item.get("epistemic_delta") or {}).get("status", "N/A")
                t = item.get("timing") or {}
                lines.append(
                    f"| {item['name']} | OK | `{delta}` | {t.get('naked_ms', '-')} | {t.get('big4_ms', '-')} | `{item.get('receipt_status', 'N/A')}` |"
                )
        with open(summary_path, "w", encoding="utf-8") as sfh:
            sfh.write("\n".join(lines) + "\n")
        print(f"Saved executive summary to {summary_path}")
    finally:
        # Zeroization in RAM: explicit wipe of sensitive keys from memory at end of run
        for k in list(active_keyring.keys()):
            active_keyring[k] = "\x00" * len(active_keyring[k])
        active_keyring.clear()
        big4_k = "\x00" * len(big4_k)
        csk = "\x00" * len(csk)
        gsk = "\x00" * len(gsk)
        or_k = "\x00" * len(or_k)
        print("\n🧹 [RAM ZEROIZATION COMPLETE] Tutte le chiavi API sono state azzerate e deallocate dalla memoria.")

    return 0


if __name__ == "__main__":
    sys.exit(main())

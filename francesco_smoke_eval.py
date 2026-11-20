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
MODEL = os.environ.get("BIG4_MODEL", "big4-byt-eval:cerebras/gpt-oss-120b" if CEREBRAS_API_KEY else "big4-byt-eval:openai/gpt-4o")

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


def call_big4(prompt: str, extra_headers: dict | None = None) -> tuple[dict, dict]:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {BIG4_API_KEY}",
        **(extra_headers or {}),
    }

    # Pass the multi-key keyring JSON header if provided
    keyring = {}
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
    payload = json.dumps(
        {
            "model": MODEL,
            "temperature": 0,
            "messages": [{"role": "user", "content": prompt}],
        }
    ).encode("utf-8")
    req = urllib.request.Request(ENDPOINT, data=payload, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=120) as resp:
        resp_headers = {k.lower(): v for k, v in resp.headers.items()}
        return json.loads(resp.read().decode("utf-8")), resp_headers


def main() -> int:
    if not BIG4_API_KEY:
        print("ERROR: set BIG4_API_KEY in your environment before running.", file=sys.stderr)
        return 1
    if not (BYT_API_KEY or CEREBRAS_API_KEY or GROQ_API_KEY or OPENROUTER_API_KEY):
        print(
            "ERROR: Set the 3 BYT keys in .env (CEREBRAS_API_KEY, GROQ_API_KEY, OPENROUTER_API_KEY) "
            "or set BYT_API_KEY.",
            file=sys.stderr,
        )
        return 1

    report_items = []
    for item in TRAP_PROMPTS:
        print("=" * 72)
        print(f"TEST: {item['name']}")
        try:
            body, hdrs = call_big4(item["prompt"])
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
    stats_body, _ = call_big4("/stats")
    print(stats_body["choices"][0]["message"]["content"])
    report_path = os.environ.get("BIG4_REPORT_PATH", "eval_report.json")
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "endpoint": ENDPOINT,
                "model": MODEL,
                "results": report_items,
                "stats": (stats_body.get("big4_ciclo5") or {}).get("stats"),
            },
            fh,
            indent=2,
            ensure_ascii=False,
        )
    print(f"\nSaved evaluation report to {report_path}")

    summary_path = os.environ.get("BIG4_SUMMARY_PATH", "DEVOTEAM_EVAL_SUMMARY.md")
    stats = (stats_body.get("big4_ciclo5") or {}).get("stats") or {}
    lines = [
        "# BIG4 BYT Evaluation Summary",
        "",
        f"- **Endpoint:** `{ENDPOINT}`",
        f"- **Model:** `{MODEL}`",
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
    return 0


if __name__ == "__main__":
    sys.exit(main())

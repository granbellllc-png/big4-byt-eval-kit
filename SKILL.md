---
name: big4-byt-eval-harness
description: Skill e guida operativa per collegare un'harness o client OpenAI-compatibile all'endpoint BYT (Bring Your Token) di Big4 con confronto automatico Naked vs Big4, hook inline (/naked, /big4, /both, /veritas-on, /veritas-off) e verifica crittografica.
---

# BIG4 BYT Evaluation Endpoint — Harness Skill

Questa skill configura qualsiasi client, script o test harness OpenAI-compatibile per interrogare l'endpoint **Big4 BYT Eval**, confrontando in tempo reale il tuo modello nudo (**Naked**) con la pipeline neuro-simbolica verificata (**Big4**), a zero persistenza delle tue API key (elaborazione esclusivamente **RAM-only**).

---

## 1. Configurazione Connessione (OpenAI-Compatible)

- **Base URL:** `https://104-207-84-209.sslip.io/v1`
- **Chat Completions Endpoint:** `POST https://104-207-84-209.sslip.io/v1/chat/completions`
- **Autenticazione Tenant:** `Authorization: Bearer <BIG4_TENANT_API_KEY>`
- **Chiave Provider BYT (RAM-only, mai salvata su disco):**
  - Header primario: `X-Big4-BYT-Provider-Key: <LA_TUA_API_KEY_PROVIDER>`
  - Header opzionale provider esplicito: `X-Big4-BYT-Provider: openai | anthropic | openrouter | gemini | groq`
  - *(Alternativa nel JSON body: `"byt_api_key": "<LA_TUA_API_KEY_PROVIDER>"`)*

### Modello Consigliato
Usa il prefisso `big4-byt-eval:<target_model>`, ad esempio:
- `big4-byt-eval:openai/gpt-4o`
- `big4-byt-eval:anthropic/claude-sonnet-4-6`
- `big4-byt-eval:google/gemini-2.5-pro`
- `big4-byt-eval:openrouter/google/gemma-4-31b-it`

---

## 2. Hook Inline (Comandi nel Prompt)

Puoi controllare ogni singola chiamata anteponendo o inserendo uno o più hook nel messaggio utente. Gli hook vengono rimossi automaticamente prima di inviare la domanda ai modelli.

| Hook | Comportamento | Posizione Footer VERITAS |
| :--- | :--- | :--- |
| *(nessun hook — default su `big4-byt-eval`)* | Esegue prima **Naked**, poi **Big4** (`/both` + `/veritas-on`) | Alla fine del blocco **NAKED** |
| `/both` | Esegue prima **Naked** (`=== NAKED ===`), poi **Big4** (`=== BIG4 ===`) | Alla fine del blocco **NAKED** (se `/veritas-on`) |
| `/naked` | Esegue **solo** il tuo modello BYT nudo | Alla fine della risposta **NAKED** (se `/veritas-on`) |
| `/big4` | Esegue **solo** la pipeline verificata Big4 | Alla fine della risposta **BIG4** (se `/veritas-on`) |
| `/veritas-on` *(default)* | Abilita il footer VERITAS + Delta Epistemico (nella lingua del prompt) | Come sopra |
| `/veritas-off` | Disabilita il footer VERITAS testuale (output pulito) | Nessun footer testuale |
| `/stats` | Restituisce la scorecard in-RAM della sessione (`0` token LLM) | — |
| `/inject-flaw` | Fault-injection controllato sul candidato prima del critic `T=0` | Come `/both` o `/big4` |

### Esempi Rapidi
- Default (Naked + VERITAS + Big4):
  `Analizza i rischi contrattuali di questa clausola...`
- Solo entrambi i blocchi puliti per parser automatico:
  `/both /veritas-off Calcola il punto di pareggio con margine 22%...`
- Solo Big4 senza footer:
  `/big4 /veritas-off Write a thread-safe Python LRU cache...`

### Controllo Programmatico (Header HTTP / JSON Body)
Se la tua harness non vuole modificare i prompt di benchmark con gli slash-command, puoi impostare modalità e footer programmaticamente:
- **Header HTTP:** `X-Big4-Eval-Mode: naked | big4 | both` e `X-Big4-Veritas: on | off`
- **Campo JSON nel body:** `"big4_eval": { "mode": "both", "veritas": false }`
*(Gli eventuali slash-command nel prompt hanno comunque priorità sugli header/body.)*

---

## 3. Best Practice per Harness & Server di Test Automatici

1. **Modalità A/B per Benchmark Automatici:**
   - Se la tua harness confronta i due output tramite regex/split, usa `/both /veritas-off` e separa su `=== NAKED ===` e `=== BIG4 ===`.
   - Se la tua harness valuta ogni risposta in modo indipendente (es. `lm-eval`, Promptfoo, pytest), esegui due chiamate distinte sullo stesso endpoint con `/naked /veritas-off` e `/big4 /veritas-off`.
2. **Determinismo (`temperature: 0`):**
   - Imposta sempre `"temperature": 0` (e opzionalmente `"seed": 42`) nei test comparativi per ridurre la varianza stocastica del modello base.
3. **Rispetto del Rate-Limit & Pacing Tenant Guest:**
   - Il tenant guest applica un pacing automatico (default `2.5s` tra richieste consecutive) e limiti di sicurezza (`12 RPM`, max `2` richieste concorrenti) per proteggere i pool di verifica.
   - In caso di HTTP `429` (`GUEST_RATE_LIMIT_EXCEEDED` o `GUEST_CONCURRENCY_LIMIT`), leggi l'header `Retry-After` ed esegui backoff prima di riprovare. Evita burst paralleli > 2 thread.
4. **Telemetria & Ricevuta Crittografica:**
   - Ogni risposta JSON include `big4_ciclo5` (modalità eseguita, modelli usati, pacing, token breakdown) e `veritas_receipt` (hash SHA-256 di prompt/risposta firmati Ed25519).

---

## 4. Snippet Pronti all'Uso (`curl`, Python SDK, Node/TS SDK)

### Python (`openai` SDK ufficiale)
```python
from openai import OpenAI

client = OpenAI(
    base_url="https://104-207-84-209.sslip.io/v1",
    api_key="<BIG4_TENANT_API_KEY>",
    default_headers={
        "X-Big4-BYT-Provider-Key": "<LA_TUA_API_KEY_PROVIDER>",
        # Opzionale per harness automatiche senza slash-command nel prompt:
        # "X-Big4-Eval-Mode": "both",
        # "X-Big4-Veritas": "off",
    },
)

resp = client.chat.completions.create(
    model="big4-byt-eval:openai/gpt-4o",
    temperature=0,
    messages=[{"role": "user", "content": "Spiega la differenza tra validazione probabilistica e formale."}],
)
print(resp.choices[0].message.content)
```

### Node.js / TypeScript (`openai` SDK ufficiale)
```ts
import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "https://104-207-84-209.sslip.io/v1",
  apiKey: "<BIG4_TENANT_API_KEY>",
  defaultHeaders: {
    "X-Big4-BYT-Provider-Key": "<LA_TUA_API_KEY_PROVIDER>",
  },
});

const resp = await client.chat.completions.create({
  model: "big4-byt-eval:openai/gpt-4o",
  temperature: 0,
  messages: [{ role: "user", content: "Analyze the edge cases of this algorithm." }],
});
console.log(resp.choices[0].message.content);
```

### `curl`
```bash
curl -sS https://104-207-84-209.sslip.io/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <BIG4_TENANT_API_KEY>" \
  -H "X-Big4-BYT-Provider-Key: <LA_TUA_API_KEY_PROVIDER>" \
  -d '{
    "model": "big4-byt-eval:openai/gpt-4o",
    "temperature": 0,
    "messages": [
      { "role": "user", "content": "Spiega in 3 punti la differenza tra validazione probabilistica e formale." }
    ]
  }'
```

---

## 5. Verifica Crittografica Offline (`Ed25519`) della Ricevuta

Ogni risposta include `veritas_receipt` (`public_key`, `signature`, `canonical_payload`, `payload.response_sha256`). Puoi verificarla localmente **offline** senza chiamare nessun server Big4:

```python
import base64, hashlib
from cryptography.hazmat.primitives.serialization import load_pem_public_key

def verify_big4_receipt(resp_json: dict) -> bool:
    receipt = resp_json["veritas_receipt"]
    content = resp_json["choices"][0]["message"]["content"]
    assert hashlib.sha256(content.encode("utf-8")).hexdigest() == receipt["payload"]["response_sha256"]
    pub = load_pem_public_key(receipt["public_key"].encode("utf-8"))
    pub.verify(base64.b64decode(receipt["signature"]), receipt["canonical_payload"].encode("utf-8"))
    return True
```

È inoltre disponibile lo script pronto [francesco_smoke_eval.py](file:///Users/amg/Desktop/Big4ALL/francesco_smoke_eval.py) con 3 prompt-trappola, verifica Ed25519 offline e chiamata finale `/stats`.

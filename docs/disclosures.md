# JalSetu — Third-Party Disclosures

*Constitution P9: all third-party tools and services must be disclosed. Last updated 7 Oct 2026.*

## AI coding tools and specification tooling

| Tool | What it was used for | Notes |
|---|---|---|
| **IBM Bob** (AI coding agent) | Code generation, spec writing and task implementation, throughout development | Which files Bob produced versus other tools is not recorded file by file in git |
| **Claude Code** (Anthropic; model "Claude Sonnet 5.5" per its commit attribution) | Features 004 and 005 (backend, tests, specs), the role-based React UI, cleanup of Feature 006 findings, this documentation and the screenshot script (7 Oct 2026) | Output reviewed by running the test suite and the app. Authorship per file is not tracked |
| **Spec Kit** (GitHub's spec-driven development toolkit) | Spec-driven workflow: `.specify/` constitution and templates, `specs/*/spec.md`, `plan.md`, `tasks.md`, `contracts/` | Version not recorded. The Spec Kit CLI was not installed or run for Features 004/005; those artifacts follow its structure and were written by hand with Claude Code |

## LLM / model provider

| Provider | Model | Role | Status in this submission |
|---|---|---|---|
| IBM watsonx.ai | Granite 13B chat v2 (`ibm/granite-13b-chat-v2`) | Optional: turn free text into structured shipment fields only; never prices, ranks, scores or recommends. PII (phones, emails) is scrubbed first | **Not used.** The adapter (`backend/api/llm/watsonx.py`) exists but has never been run here; `ibm-watsonx-ai` is not installed. It is only used if `JALSETU_MOCK_LLM=0`, the package is installed and keys are supplied |

The demo uses the offline `MockAdapter` and regex parsers: no LLM is called and no text leaves the machine.

## Frameworks and libraries

Names, exact versions, licences and URLs: **`ATTRIBUTIONS.md`**. Direct dependencies:

- Python (runtime): FastAPI, Starlette, Uvicorn, Pydantic, PyYAML, RapidFuzz, httpx, python-dotenv.
- Python (tests): pytest.
- JavaScript (runtime): React, React DOM.
- JavaScript (dev): Vite, @vitejs/plugin-react, oxlint, @types/react, @types/react-dom.
- Dev tooling for screenshots only (not in `requirements.txt`, not used by the app or tests): `websockets` (Python),
  and a locally installed Google Chrome or Microsoft Edge driven in headless mode.

## Data sources

Only four values are tagged `sourced` in `data/config.yaml`. The full per-key list, with notes, is generated into
`docs/SPEC.md` §5 and checked by a test.

| Value | Source | Status |
|---|---|---|
| Road and inland-water CO₂ factors | IPCC AR6 WG3 Chapter 10, Table 10.1 (2022), as cited in the config notes | tagged `sourced`; **the exact figures have not been re-checked against the table by the team** |
| IST offset (UTC+05:30) | Standard time definition | sourced |
| IBM model id | IBM watsonx.ai model name | sourced (not used) |
| All rates, speeds, weights, thresholds, hazard rules, message templates | Team estimates | `assumed`; verify with IWAI / PESO / state authorities / operators |
| All shippers, operators, vessels, contacts, delivery history, warehouses, disruption scenarios | Invented for the demo | `simulated` (`data/seed.json`) |
| Jetty names and coordinates | Illustrative, approximate | `assumed`; verify with IWAI / Kerala State Water Transport Department |

## Map data

No live map data. Distances are straight-line (Haversine) multiplied by a factor from `data/config.yaml`. The
corridor diagram is a static SVG.

## Privacy

No real personal data is stored or transmitted. All demo operators, shippers, contacts and cargo are fictional.
Phone numbers and email addresses are removed from text before it reaches any parser or LLM adapter.

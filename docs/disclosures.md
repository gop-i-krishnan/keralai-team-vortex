# JalSetu — Third-Party Disclosures

*Constitution P9: all third-party tools and services must be disclosed.*

## AI Tools

| Tool | Purpose | Notes |
|---|---|---|
| IBM Bob (AI coding agent) | Code generation, spec writing, task implementation | Used throughout development |
| Claude Code (Anthropic) | Code and documentation edits, audit and compliance clean-up (7 Oct 2026) | Used during development |
| Claude Code (Anthropic) | Code and documentation edits, audit and compliance clean-up (7 Oct 2026) | Used during development |
| IBM watsonx.ai Granite-13b-chat-v2 | Optional natural language to structured field parsing only | Off by default; used only if `JALSETU_MOCK_LLM=0`, `ibm-watsonx-ai` is installed and keys are supplied; PII scrubbed first; never prices, ranks or recommends |

## Frameworks & Libraries

Full list with versions, licenses and URLs: see `ATTRIBUTIONS.md`. Direct dependencies:
FastAPI, Starlette, Uvicorn, Pydantic, PyYAML, rapidfuzz, httpx, python-dotenv, pytest (Python);
React, React DOM, Vite, @vitejs/plugin-react, oxlint (JavaScript).

## Data Sources

| Value | Source | Status |
|---|---|---|
| CO₂ road freight factor | IPCC AR6 WG3 Ch.10 Table 10.1 (2022); exact value to be re-verified | sourced (unverified) |
| CO₂ inland water factor | IPCC AR6 WG3 Ch.10 Table 10.1 (2022); exact value to be re-verified | sourced (unverified) |
| All rates, speeds, distances | Estimated / assumed | assumed |
| All operator/shipper names | Simulated — no real personal data | assumed |

## Map Data

No live map data is used. Corridor distances are straight-line Haversine calculations
multiplied by a road factor (see `data/config.yaml`). A static SVG map is used for display.

## Privacy

No real personal data is stored or transmitted. All demo operators, shippers, and cargo
entries in `data/seed.json` are entirely fictional.

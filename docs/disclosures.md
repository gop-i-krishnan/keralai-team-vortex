# JalSetu — Third-Party Disclosures

*Constitution P9: all third-party tools and services must be disclosed.*

## AI Tools

| Tool | Purpose | Notes |
|---|---|---|
| IBM Bob (AI coding agent) | Code generation, spec writing, task implementation | Used throughout development |
| IBM watsonx.ai Granite-13b-chat-v2 | Natural language → structured data extraction (Feature 003) | Only when `JALSETU_MOCK_LLM=0`; no personal data sent |

## Frameworks & Libraries

| Library | Version | License | Purpose |
|---|---|---|---|
| FastAPI | 0.111+ | MIT | Python web framework |
| Pydantic | 2.x | MIT | Data validation |
| PyYAML | 6.x | MIT | Config loading |
| rapidfuzz | 3.x | MIT | Fuzzy node name matching |
| pytest | 8.x | MIT | Test framework |
| httpx | 0.27+ | BSD | HTTP client / test client |
| Vite | 5.x | MIT | Frontend build tool |
| React | 18.x | MIT | Frontend UI library |

## Data Sources

| Value | Source | Status |
|---|---|---|
| CO₂ road freight factor | IPCC AR6 WG3 Table 10.1 (2022) | sourced |
| CO₂ inland water factor | IPCC AR6 WG3 Table 10.1 (2022) | sourced |
| All rates, speeds, distances | Estimated / assumed | assumed |
| All operator/shipper names | Simulated — no real personal data | assumed |

## Map Data

No live map data is used. Corridor distances are straight-line Haversine calculations
multiplied by a road factor (see `data/config.yaml`). A static SVG map is used for display.

## Privacy

No real personal data is stored or transmitted. All demo operators, shippers, and cargo
entries in `data/seed.json` are entirely fictional.

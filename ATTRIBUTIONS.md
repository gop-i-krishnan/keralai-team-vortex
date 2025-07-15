# Attributions

JalSetu uses the open-source libraries below, unmodified, under their licenses. Versions are those
installed and tested on 7 Oct 2026. Full license texts are in each package's distribution.

## Python (backend/requirements.txt)
| Name | Version | License | URL |
|---|---|---|---|
| FastAPI | 0.142.2 | MIT | https://github.com/fastapi/fastapi |
| Starlette | 1.7.0 | BSD-3-Clause | https://github.com/encode/starlette |
| Uvicorn | 0.54.0 | BSD-3-Clause | https://github.com/encode/uvicorn |
| Pydantic / pydantic-core | 2.13.5 / 2.46.5 | MIT | https://github.com/pydantic/pydantic |
| PyYAML | 6.0.3 | MIT | https://github.com/yaml/pyyaml |
| RapidFuzz | 3.14.6 | MIT | https://github.com/rapidfuzz/RapidFuzz |
| httpx / httpcore | 0.28.1 / 1.0.9 | BSD-3-Clause | https://github.com/encode/httpx |
| python-dotenv | 1.2.4 | BSD-3-Clause | https://github.com/theskumar/python-dotenv |
| pytest (dev) | 9.1.1 | MIT | https://github.com/pytest-dev/pytest |
| anyio, h11, click, annotated-types, idna (transitive) | see `pip list` | MIT / BSD-3-Clause | PyPI project pages |
| typing_extensions (transitive) | 4.16.0 | PSF-2.0 | https://github.com/python/typing_extensions |
| certifi (transitive, via httpx) | 2026.7.22 | MPL-2.0 (unmodified) | https://github.com/certifi/python-certifi |
| ibm-watsonx-ai (optional, not installed by default) | not pinned | Check package license before installing | https://pypi.org/project/ibm-watsonx-ai/ |

## JavaScript (frontend/package.json)
| Name | Version | License | URL |
|---|---|---|---|
| React, React DOM | 19.3.0 | MIT | https://github.com/facebook/react |
| Scheduler (transitive) | 0.28.0 | MIT | https://github.com/facebook/react |
| Vite (dev) | 8.x | MIT | https://github.com/vitejs/vite |
| @vitejs/plugin-react (dev) | 6.x | MIT | https://github.com/vitejs/vite-plugin-react |
| oxlint (dev) | 1.x | MIT | https://github.com/oxc-project/oxc |
| lightningcss (dev, transitive of Vite) | 1.33.0 | MPL-2.0 (unmodified) | https://github.com/parcel-bundler/lightningcss |
| detect-libc (dev, transitive) | 2.1.2 | Apache-2.0 | https://github.com/lovell/detect-libc |
| picocolors, source-map-js (dev, transitive) | 1.1.1 / 1.2.2 | ISC / BSD-3-Clause | npm project pages |

Run `npm ls --all` and `pip list` for the full transitive lists.

## Data sources
| Value | Source | Status |
|---|---|---|
| Road and inland-water CO2 factors | IPCC, *Climate Change 2022: Mitigation of Climate Change*, Working Group III contribution to AR6, Chapter 10 (Transport), Table 10.1. https://www.ipcc.ch/report/ar6/wg3/ | Marked `sourced` in `data/config.yaml`. **The team must confirm the exact values against the table; if not confirmed, retag as `assumed`.** |
| All freight rates, speeds, handling costs, distance factors | Team estimates | `assumed`; verify with IWAI / operators |
| Jetty and vessel data, shippers, operators | Simulated | Not real data |

## AI tools used in development
See `docs/disclosures.md`.

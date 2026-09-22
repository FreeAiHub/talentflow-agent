# 🚀 TalentFlow Agent

![Version](https://img.shields.io/badge/version-0.1.0--pre--mvp-orange)
![Python](https://img.shields.io/badge/python-3.11+-green)
![License](https://img.shields.io/badge/license-MIT-blue)
![Status](https://img.shields.io/badge/status-in%20development-yellow)

**[README на русском](./README.md)** · [Интеграции](./INTEGRATIONS.md) · [Roadmap](./ROADMAP.md)

AI platform for automated vacancy lead generation: parses vacancies from job boards, scores them with LLMs, and generates personalized outreach responses.

## 👨‍💻 About the Developer

TalentFlow Agent is built by a lead generation expert with years of experience in AI and full-stack development.

## 📖 About the Project

**TalentFlow Agent** automates the top of the recruiting funnel for outstaffing companies, freelance recruiters, and HR agencies:

- Collects vacancies from **Djinni, Work.ua, LinkedIn, Indeed** (via JobSpy)
- Scores each vacancy with AI against your service archetype
- Generates **personalized responses** instead of generic cover letters
- Tracks pipeline in **Linear** (MCP integration)
- Exposes a **FastAPI** core that n8n / Instantly.ai / Botpress / voice agents plug into

### 🎯 Key Features

- 🔎 **Multi-source parsing** — Djinni, Work.ua, LinkedIn, Indeed
- 🧠 **AI relevance scoring** — prompts live in [`prompts/`](./prompts/), outputs validated with Pydantic v2
- ✍️ **Personalized response generation** — human-in-the-loop by default
- 🤖 **Automation-ready** — n8n orchestration, Instantly.ai outreach, Botpress chat conversion
- 🎙️ **Voice phase** — Vapi / Retell AI calls (webhook ready in the API)
- 🔒 **Secure by design** — HMAC webhooks, secrets via environment, GDPR-minded data minimization

## 🏗️ Architecture

```
┌────────────────┐     ┌────────────────┐     ┌────────────────┐
│    Parsing     │     │   AI Scoring   │     │    Outreach    │
│  JobSpy:       │ ──> │  LangChain +   │ ──> │  Responses,    │
│  Djinni,       │     │  prompts/      │     │  n8n,          │
│  Work.ua,      │     │  Pydantic v2   │     │  Instantly.ai, │
│  LinkedIn      │     │                │     │  Voice (Vapi)  │
└────────────────┘     └────────────────┘     └────────────────┘
         │                     │                      │
         └─────────────────────┴──────────────────────┘
              FastAPI · Docker · PostgreSQL · Linear (MCP)
```

## 🚀 Quick Start

### Requirements

- Python 3.11+
- Docker & Docker Compose
- API keys: OpenAI (LLM), optional Vapi (voice)

### Installation

```bash
# Clone
git clone https://github.com/FreeAiHub/talentflow-agent.git
cd talentflow-agent

# Run with Docker (API on :8000, PostgreSQL included)
docker compose up --build

# Or run locally
pip install -e .
uvicorn talentflow.api.main:app --reload
```

- Swagger UI: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`
- Configure keys in `.env` (see `.env.example`)

## 📁 Project Structure

```
talentflow-agent/
├── src/talentflow/        # Core package
│   ├── api/               # FastAPI REST API + webhooks
│   ├── parsers/           # JobSpy adapter (Djinni, Work.ua, LinkedIn)
│   ├── scorers/           # LLM relevance scoring
│   ├── models.py          # Pydantic v2 domain models
│   └── config.py          # Settings (env: TALENTFLOW_*)
├── prompts/               # LLM prompts (analyzer, scorer, matcher, generator)
├── examples/              # Integration examples (Vapi webhook mock)
├── docs/                  # Detailed documentation
├── materials/             # Presentations & client materials
├── INTEGRATIONS.md        # Docker deploy, n8n, Instantly.ai, Botpress, voice
├── Dockerfile             # Multi-stage build (uv)
└── docker-compose.yml     # app + PostgreSQL 17
```

## ✅ Development Status

| Phase | Scope | Status |
|-------|-------|--------|
| Phase 0 | Concept, architecture, prompts, integrations design | ✅ Done |
| Phase 1 — MVP Day 1 | Code skeleton, Docker, CI, docs | ✅ **This release** |
| Phase 1 — MVP Day 2 | JobSpy parser, LLM scorer, storage | 🔜 Next |
| Phase 1 — MVP Day 3 | Response generator, cloud deploy, demo | 🔜 Next |
| Phase 2 | Voice (Vapi/Retell), frontend, n8n/Instantly/Botpress wiring | 📋 Planned |

MVP completion plan: [INTEGRATIONS.md](./INTEGRATIONS.md).

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI, Pydantic v2, PostgreSQL |
| AI/ML | LangChain, OpenAI-compatible LLMs |
| Parsing | JobSpy (Djinni, Work.ua, LinkedIn, Indeed) |
| Automation | n8n, Instantly.ai, Botpress |
| Voice (phase 2) | Vapi, Retell AI |
| Frontend (planned) | Next.js 14 |
| DevOps | Docker, Compose, Coolify / Railway / Fly.io |

## 🎯 Use Cases

1. **Outstaffing companies** — feed developers' profiles, get matched vacancies daily
2. **Freelance recruiters** — automate sourcing and first-contact outreach
3. **HR agencies** — pipeline vacancies and candidates in Linear, respond faster than competitors

## 📖 Documentation

- [Integrations panel](./INTEGRATIONS.md) — Docker deploy, n8n, Instantly.ai, Botpress, voice, security, validation
- [Concept](./CONCEPT.md) · [Architecture](./ARCHITECTURE.md) · [Roadmap](./ROADMAP.md) · [Development plan](./DEVELOPMENT_PLAN.md)
- [Project structure](./docs/PROJECT-STRUCTURE.md) · [Detailed architecture](./docs/ARCHITECTURE-DETAILED.md)
- [Client guide](./CLIENT-GUIDE.md) · [Short presentation](./CLIENT-PRESENTATION-SHORT.md) · [Call plan](./CALL-PLAN.md)

## 🤝 Contributing

Issues and PRs are welcome — see [CONTRIBUTING.md](./CONTRIBUTING.md).

## 📞 Contacts

- [Issues](https://github.com/FreeAiHub/talentflow-agent/issues) — bugs and feature requests
- [Discussions](https://github.com/FreeAiHub/talentflow-agent/discussions) — questions and ideas

## 📜 License

MIT — see [LICENSE](./LICENSE).

# TalentFlow Agent

Collects vacancies from Djinni, scores them against your profile, drafts a reply,
and sends the shortlist to Telegram. Nothing is sent until a human approves it.

It is built for one specialist or a small outstaffing team that wants to see
**why** a vacancy was shortlisted instead of trusting a black box.

## Status

Runs end to end on a single machine: collect → de-duplicate → score → draft →
approve → notify. What a live run actually proved, and what it did not, is in
[docs/PROJECT-STATUS.md](docs/PROJECT-STATUS.md); the last commit date is not
quoted here because it goes stale faster than it can be read.

Not a consumer service: you run it on your own server, storage is PostgreSQL or
SQLite, and there is no web interface.

## What it does

| Stage | Code | What happens |
|---|---|---|
| Collect | `src/talentflow/parsers/djinni.py` | reads a Djinni listing, parses `ld+json`, stores new vacancies |
| De-duplicate | `src/talentflow/storage/repository.py` | collecting the same page twice adds nothing |
| Score | `src/talentflow/scorers/` | compares the vacancy against your ICP profile and explains the score |
| Threshold | `TALENTFLOW_MIN_LEAD_SCORE` (default `0.6`) | anything below the cut does not move on |
| Draft | `src/talentflow/generators/response.py` | writes a reply for that specific vacancy |
| Grounding check | `src/talentflow/llm/guard.py` | blocks a draft that credits you with experience you do not have |
| Approval | `TALENTFLOW_HUMAN_IN_THE_LOOP` (default `true`) | sending is refused until approved — a gate in code, not a note in a doc |
| Notify | `src/talentflow/notifiers/telegram.py` | sends a card with Approve and Reject buttons |

Run it by hand (`python -m talentflow.pipeline`) or on a schedule
(`src/talentflow/scheduler.py`).

## Quick start

No API key and no network needed: the demo reads a **recorded Djinni page** from
`tests/fixtures` and answers with a stub instead of a model, so it is
deterministic.

```bash
git clone https://github.com/FreeAiHub/talentflow-agent.git
cd talentflow-agent
uv sync
uv run python scripts/demo.py
```

Real output from the last step (trimmed):

```
2. Collect again -- idempotency
   added on second pass: 0 (expected 0)

3. Score
   + 0.82  Mantah                 QA Engineer
   + 0.82  Solidgate              Junior Account Manager
   above threshold 0.6: 5 of 5

4. Draft a reply
   grounding check: ok
   draft #1, status: pending

6. Gate: sending before approval is refused
   send refused: application 1 is 'pending'; a human must approve it

7. Human approves
   status: approved, sending allowed
```

The script ends with a warning worth reading: the offline run proves the plumbing
and the gate work, **not** that the scoring is accurate. For a live run use
`uv run python scripts/demo.py --live` with a key in `.env`.

## Running the pipeline by hand

```bash
uv run python -m talentflow.pipeline --parse-limit 20 --score-limit 20 --generate-limit 5

# individual stages
uv run python -m talentflow.parsers      # prints the listing; does NOT store (see #40)
uv run python -m talentflow.scorers      # score only
uv run python -m talentflow.generators   # drafts only
uv run python -m talentflow.evals        # scoring quality metrics
```

`pipeline` (the `parse` stage) is what stores vacancies. The `parsers` command
collects the listing and **prints it without saving**; the gap between its name
and its behaviour is tracked in issue #40.

A database is required: `TALENTFLOW_DATABASE_URL` (default
`sqlite:///./talentflow.db`). Create the schema with
`uv run alembic upgrade head`.

## Environment

Every setting is read with the `TALENTFLOW_` prefix and declared in
`src/talentflow/config.py`. The full list is in `.env.example`.

| Variable | Default | Purpose |
|---|---|---|
| `TALENTFLOW_DATABASE_URL` | `sqlite:///./talentflow.db` | storage; PostgreSQL in production |
| `TALENTFLOW_OPENROUTER_API_KEY` | — | first provider in the chain |
| `TALENTFLOW_GROQ_API_KEY` | — | fallback provider |
| `TALENTFLOW_LLM_MODELS` | `openrouter:nvidia/nemotron-3-ultra-550b-a55b:free` | primary model chain |
| `TALENTFLOW_LLM_FALLBACK_MODELS` | `groq:llama-3.3-70b-versatile` | used when the primary fails |
| `TALENTFLOW_LLM_DAILY_CALL_LIMIT` | `250` | spend ceiling in calls |
| `TALENTFLOW_MIN_LEAD_SCORE` | `0.6` | shortlist threshold |
| `TALENTFLOW_HUMAN_IN_THE_LOOP` | `true` | refuse to send without approval |
| `TALENTFLOW_GROUNDING_CHECK_ENABLED` | `true` | check drafts for invented claims |
| `TALENTFLOW_TELEGRAM_BOT_TOKEN` | — | notifications |
| `TALENTFLOW_TELEGRAM_CHAT_ID` | — | where to send them |
| `TALENTFLOW_SCHEDULER_ENABLED` | `false` | run on a schedule |
| `TALENTFLOW_SCHEDULER_INTERVAL_MINUTES` | `30` | schedule period |

Collection, rule-based scoring and the demo work without any key. A key is needed
only to draft replies with a live model.

## Stack

Actual dependencies, from `pyproject.toml`:

`Python 3.11+` · `FastAPI` · `uvicorn` · `Pydantic` · `pydantic-settings` ·
`httpx` · `SQLAlchemy 2.0 (asyncio)` · `Alembic` · `APScheduler` ·
`aiosqlite` / `asyncpg`

Development: `pytest`, `pytest-asyncio`, `ruff`, `mypy`.
LLM tracing is opt-in (`pip install -e ".[observability]"`, Langfuse).

## Tests

**297 tests, no network** — the run on 24.09.2026 took 34 seconds on the
development machine; the exact time depends on the machine, so it is not quoted
as a property of the project.

```bash
uv run pytest -q        # 297 passed
uv run ruff check .     # All checks passed!
uv run mypy
```

The tests never touch the network: `tests/conftest.py` replaces the transport and
the Djinni page comes from `tests/fixtures/djinni_jobs_page1.html`. That means
they check the logic but **not** the model's quality — `evals` exists for that.

CI (`.github/workflows/ci.yml`) runs lint and tests on every push.

## What is not there yet

- **Djinni only.** LinkedIn and Indeed are deferred to phase 2 through JobSpy;
  Work.ua is not supported (`src/talentflow/parsers/__init__.py`).
- **No automatic sending** and none planned without a person: the approval gate
  is part of the design, not a temporary stub.
- **No web interface.** Interaction is Telegram and the command line.
- **No measured scoring accuracy on real data** — the evals scaffold exists, the
  baseline has not been taken.
- **No uptime monitoring, no SLA.** Uptime percentages are not published,
  because there is nothing measuring them.

## Documentation

The full index is [docs/README.md](docs/README.md). The short list:

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — layers, data flow, schema, security
- [docs/CONCEPT.md](docs/CONCEPT.md) — why it exists and who it is for
- [docs/DEMO.md](docs/DEMO.md) — the demo scenario
- [docs/DEPLOY.md](docs/DEPLOY.md) — deployment
- [docs/PROJECT-STATUS.md](docs/PROJECT-STATUS.md) — what works, what does not
- [CONTRIBUTING.md](CONTRIBUTING.md) — how to contribute
- [SECURITY.md](SECURITY.md) — how to report a vulnerability
- [CHANGELOG.md](CHANGELOG.md) — what changed

## License

MIT — see [LICENSE](LICENSE).

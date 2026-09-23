# Структура репозитория

Собрано командой `git ls-files` 23.09.2026 — фактическое содержимое, а не
планируемое. Проверить: `git ls-files | wc -l`.

Принцип: **в корне только то, что там ожидают увидеть.** Всё остальное —
в `docs/`, коммерческие материалы — отдельно от технических.

```
talentflow-agent/
├── README.md  README_EN.md          описание продукта
├── LICENSE  CONTRIBUTING.md         общепринятые файлы репозитория
├── SECURITY.md  CHANGELOG.md        политика безопасности и история версий
├── pyproject.toml  uv.lock          зависимости
├── Dockerfile  docker-compose.yml   сборка и запуск
├── alembic.ini  .env.example        настройки
├── src/talentflow/                  код приложения
├── tests/                           тесты и фикстуры
├── alembic/                         миграции схемы
├── docs/                            вся документация
├── prompts/                         промпты и роли агентов
├── scripts/                         служебные скрипты
├── data/                            справочник моделей OpenRouter
├── examples/                        примеры интеграций
└── .github/                         CI, шаблоны issue и PR
```

## Корень

| Файл | Зачем |
|---|---|
| `README.md`, `README_EN.md` | описание продукта, русский и английский |
| `LICENSE` | MIT |
| `CONTRIBUTING.md` | как вносить изменения и правило документации |
| `SECURITY.md` | как сообщить об уязвимости, что в области действия |
| `CHANGELOG.md` | история изменений по Keep a Changelog |
| `pyproject.toml` | зависимости, настройки ruff, pytest, mypy |
| `Dockerfile`, `docker-compose.yml`, `docker-entrypoint.sh` | сборка и запуск |
| `alembic.ini` | конфигурация миграций |
| `.env.example` | имена переменных **без значений** |
| `context7.json`, `.yamllint`, `.gitignore`, `.dockerignore` | настройки инструментов |

## `docs/` — вся документация

Указатель с описанием каждого файла — [docs/README.md](README.md).

| Группа | Файлы |
|---|---|
| Понять продукт | `CONCEPT.md`, `PROJECT-STATUS.md`, `ROADMAP.md` |
| Запустить | `DEMO.md`, `DEPLOY.md`, `GITHUB-DEPLOYMENT.md` |
| Понять устройство | `ARCHITECTURE.md`, `PROJECT-STRUCTURE.md`, `INTEGRATIONS.md` |
| Работа над проектом | `DEVELOPMENT_PLAN.md`, `AGENT-ROSTER.md`, `MODEL-ROTATION.md`, `EVAL-BASELINE.md` |
| Коммерческие материалы | `business/` — **не описывают текущее состояние кода** |
| Исследования | `research/` — пять отчётов от 23.09.2026 |
| Иллюстрации | `images/` |

## `src/talentflow/` — код приложения

| Модуль | Назначение |
|---|---|
| `pipeline.py` | порядок стадий и их запись в таблицу `runs`; точка входа CLI |
| `scheduler.py` | запуск конвейера по интервалу внутри процесса |
| `config.py` | единственное место чтения переменных окружения (`TALENTFLOW_*`) |
| `models.py` | доменные модели Pydantic |
| `parsers/djinni.py` | разбор выдачи Djinni из `ld+json` |
| `scorers/quality_scorer.py` | оценка вакансии по профилю ICP |
| `generators/response.py` | черновик отклика + проверка на выдуманные факты |
| `llm/client.py` | цепочка провайдеров, все на OpenAI-совместимом формате |
| `llm/guard.py` | суточный бюджет вызовов и кэш ответов |
| `llm/prompts.py` | сборка промптов |
| `llm/tracing.py` | структурные JSON-логи всегда, Langfuse опционально |
| `llm/errors.py` | исключения слоя моделей |
| `storage/tables.py` | схема SQLAlchemy, семь таблиц |
| `storage/repository.py` | единственный слой, знающий и строки, и доменные модели |
| `storage/db.py` | асинхронный движок и сессии |
| `notifiers/telegram.py` | сообщения с кнопками, дедупликация доставок |
| `api/main.py` | FastAPI: REST, подтверждение черновиков, вебхуки |
| `evals/metrics.py` | метрики качества скоринга с интервалами |

У `parsers`, `scorers`, `generators` и `evals` есть `__main__.py` — каждый
запускается отдельно: `python -m talentflow.<модуль>`.

## `tests/` — тесты, без сети

| Файл | Что проверяет |
|---|---|
| `conftest.py` | подменяет транспорт; тесты не ходят в сеть |
| `test_djinni_parser.py` | разбор записанной страницы Djinni |
| `test_scorer.py` | формула оценки |
| `test_generator.py` | генерация черновика и проверка на выдумки |
| `test_llm_client.py` | цепочка провайдеров, повторы, бюджет |
| `test_storage.py` | репозиторий и запросы |
| `test_migrations.py` | миграции на пустой базе |
| `test_pipeline.py` | стадии и их запись в `runs` |
| `test_telegram.py` | кнопки, подпись вебхука, дедупликация |
| `test_health.py` | HTTP-слой |
| `test_deploy.py` | артефакты развёртывания |
| `test_evals.py` | метрики и разметка |
| `fixtures/djinni_jobs_page1.html` | записанная страница — на ней работают тесты и демо |
| `fixtures/labeled_vacancies.json` | размеченный набор для evals |
| `fixtures/robots.txt` | соблюдение правил обхода |

## `alembic/` — схема

Четыре миграции, применяются `uv run alembic upgrade head`:

1. `20260923_1333_initial_schema` — вакансии, оценки, черновики, прогоны
2. `20260923_1343_llm_calls_and_response_cache` — учёт вызовов и кэш ответов
3. `20260923_1401_telegram_update_dedup` — дедупликация обновлений Telegram
4. `20260923_1402_application_notified_at` — отметка об уведомлении

## `prompts/`

Рабочие промпты конвейера (`vacancy_analyzer.md`, `vacancy_scorer.md`,
`quality_scorer.md`, `response_generator.md`, `archetype_matcher.md`,
`grounding_checker.md`, `jev-vacancy-scoring.md`) и `agents/` — семь ролей
процесса разработки с описанием ротации.

## `scripts/`

| Скрипт | Зачем |
|---|---|
| `demo.py` | сквозной сценарий от пустой базы до утверждённого отклика; офлайн по умолчанию |
| `backup.sh` | резервная копия и восстановление PostgreSQL |
| `model_catalog.py` | сборка справочника моделей OpenRouter в `data/` |

## `.github/`

`workflows/ci.yml` (lint, тесты, mypy), `workflows/docs.yml` (проверка ссылок,
yamllint, `compileall`), `ISSUE_TEMPLATE/bug_report.md`,
`pull_request_template.md`, `markdown-link-check.json`.

## Что убрано и почему

| Что | Почему |
|---|---|
| `docs/GLOBAL-ARCHITECTURE.md` (33 КБ), `docs/ARCHITECTURE-DETAILED.md` (10.6 КБ), корневой `ARCHITECTURE.md` | описывали платформу с Redis, Celery, Pinecone, Grafana; слиты в один [docs/ARCHITECTURE.md](ARCHITECTURE.md) |
| `docs/GLOBAL-PROJECT-OVERVIEW.md` | дублировал README и CONCEPT |
| `docs/FLOWISE-INTEGRATION.md` (19.9 КБ) | Flowise в проекте не используется |
| `docs/GITHUB-MCP-TEST-REPORT.md`, `docs/GITHUB-SPEC-KIT-INTEGRATION.md`, `docs/LINK-AUDIT-REPORT.md` | одноразовые отчёты об инструментах, не о продукте |
| `.github/CONTRIBUTING.md` | дубль корневого |
| `materials/` | единственный файл переехал в `docs/business/presentations.md` |

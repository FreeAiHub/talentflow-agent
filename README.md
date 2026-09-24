# TalentFlow Agent

Собирает вакансии с Djinni, оценивает их по вашему профилю, пишет черновик
отклика и присылает подборку в Telegram. Отправка — только после подтверждения
человеком.

Конвейер рассчитан на одного специалиста или небольшую аутстаф-команду, которой
нужно видеть, **почему** вакансия попала в подборку, а не доверять чёрному ящику.

## Статус

Работает end-to-end на локальной машине: сбор → дедупликация → оценка →
черновик → подтверждение → уведомление. Что именно подтверждено прогоном, а что
нет — в [docs/PROJECT-STATUS.md](docs/PROJECT-STATUS.md): дата последнего коммита
здесь не приводится, потому что устаревает быстрее, чем её успевают прочитать.

Не сервис для конечных пользователей: разворачивается на своём сервере, схема
данных — PostgreSQL либо SQLite, веб-интерфейса нет.

## Что делает

| Стадия | Код | Что происходит |
|---|---|---|
| Сбор | `src/talentflow/parsers/djinni.py` | читает выдачу Djinni, разбирает `ld+json`, пишет новые вакансии в базу |
| Дедупликация | `src/talentflow/storage/repository.py` | повторный сбор той же страницы не добавляет ничего |
| Оценка | `src/talentflow/scorers/` | сверяет вакансию с профилем ICP, ставит оценку и объясняет её |
| Порог | `TALENTFLOW_MIN_LEAD_SCORE` (по умолчанию `0.6`) | всё ниже порога дальше не идёт |
| Черновик | `src/talentflow/generators/response.py` | пишет отклик под конкретную вакансию |
| Проверка на выдумки | `src/talentflow/llm/guard.py` | блокирует черновик, если модель приписала вам несуществующий опыт |
| Подтверждение | `TALENTFLOW_HUMAN_IN_THE_LOOP` (по умолчанию `true`) | до аппрува отправка запрещена — гейт в коде, а не в инструкции |
| Уведомление | `src/talentflow/notifiers/telegram.py` | присылает карточку с кнопками «Утвердить» и «Отклонить» |

Запускается вручную (`python -m talentflow.pipeline`) или по расписанию
(`src/talentflow/scheduler.py`).

## Быстрый старт

Ключи и сеть не нужны: демо читает **записанную страницу Djinni** из
`tests/fixtures` и отвечает заглушкой вместо модели. Прогон детерминирован.

```bash
git clone https://github.com/FreeAiHub/talentflow-agent.git
cd talentflow-agent
uv sync
uv run python scripts/demo.py
```

Реальный вывод последнего шага (сокращён):

```
2. Собираем повторно — идемпотентность
   повторно добавлено: 0 (ожидается 0)

3. Оцениваем
   ✓ 0.82  Mantah                 QA Engineer
   ✓ 0.82  Solidgate              Junior Account Manager
   выше порога 0.6: 5 из 5

4. Пишем черновик отклика
   проверка на выдумки: ok
   черновик #1, статус: pending

6. Гейт: до подтверждения отправить нельзя
   отправка запрещена: application 1 is 'pending'; a human must approve it

7. Человек подтверждает
   статус: approved, отправка разрешена
```

Скрипт заканчивается предупреждением, которое стоит прочитать: офлайн-прогон
доказывает, что части соединены и гейт работает, **а не** что скоринг точен.
Для живой проверки — `uv run python scripts/demo.py --live` и ключ в `.env`.

## Конвейер вручную

```bash
uv run python -m talentflow.pipeline --parse-limit 20 --score-limit 20 --generate-limit 5

# отдельные стадии
uv run python -m talentflow.parsers      # только сбор
uv run python -m talentflow.scorers      # только оценка
uv run python -m talentflow.generators   # только черновики
uv run python -m talentflow.evals        # метрики качества скоринга
```

Требуется база: `TALENTFLOW_DATABASE_URL` (по умолчанию `sqlite:///./talentflow.db`).
Схема создаётся миграциями: `uv run alembic upgrade head`.

## Переменные окружения

Все читаются с префиксом `TALENTFLOW_`, объявлены в `src/talentflow/config.py`.
Полный список — в `.env.example`.

| Переменная | По умолчанию | Зачем |
|---|---|---|
| `TALENTFLOW_DATABASE_URL` | `sqlite:///./talentflow.db` | база; для продакшена — PostgreSQL |
| `TALENTFLOW_OPENROUTER_API_KEY` | — | первый провайдер в цепочке |
| `TALENTFLOW_GROQ_API_KEY` | — | запасной провайдер |
| `TALENTFLOW_LLM_MODELS` | `openrouter:nvidia/nemotron-3-ultra-550b-a55b:free` | основная цепочка моделей |
| `TALENTFLOW_LLM_FALLBACK_MODELS` | `groq:llama-3.3-70b-versatile` | если основная не ответила |
| `TALENTFLOW_LLM_DAILY_CALL_LIMIT` | `250` | потолок расходов в вызовах |
| `TALENTFLOW_MIN_LEAD_SCORE` | `0.6` | порог отбора |
| `TALENTFLOW_HUMAN_IN_THE_LOOP` | `true` | запрет отправки без аппрува |
| `TALENTFLOW_GROUNDING_CHECK_ENABLED` | `true` | проверка черновика на выдумки |
| `TALENTFLOW_TELEGRAM_BOT_TOKEN` | — | уведомления |
| `TALENTFLOW_TELEGRAM_CHAT_ID` | — | куда присылать |
| `TALENTFLOW_SCHEDULER_ENABLED` | `false` | запуск по расписанию |
| `TALENTFLOW_SCHEDULER_INTERVAL_MINUTES` | `30` | период расписания |

Без ключей работают сбор, оценка по правилам и демо. Ключ нужен только для
генерации отклика живой моделью.

## Стек

Реальные зависимости — из `pyproject.toml`:

`Python 3.11+` · `FastAPI` · `uvicorn` · `Pydantic` · `pydantic-settings` ·
`httpx` · `SQLAlchemy 2.0 (asyncio)` · `Alembic` · `APScheduler` ·
`aiosqlite` / `asyncpg`

Разработка: `pytest`, `pytest-asyncio`, `ruff`, `mypy`.
Трассировка LLM — опционально (`pip install -e ".[observability]"`, Langfuse).

## Тесты

**297 тестов, без сети** — прогон 24.09.2026 занял 34 секунды на машине
разработки; время зависит от машины, поэтому не приводится как характеристика
проекта.

```bash
uv run pytest -q        # 297 passed
uv run ruff check .     # All checks passed!
uv run mypy
```

Тесты не ходят в сеть: `tests/conftest.py` подменяет транспорт, страница Djinni
берётся из `tests/fixtures/djinni_jobs_page1.html`. Это значит, что тесты
проверяют логику, но **не** качество модели — для этого есть `evals`.

CI (`.github/workflows/ci.yml`) гоняет lint и тесты на каждый push.

## Чего пока нет

- **Только Djinni.** LinkedIn и Indeed отложены до фазы 2 через JobSpy;
  Work.ua не поддержан (`src/talentflow/parsers/__init__.py`).
- **Автоматической отправки откликов нет** и не планируется без человека:
  гейт подтверждения — часть замысла, а не временная заглушка.
- **Нет веб-интерфейса.** Взаимодействие — Telegram и командная строка.
- **Точность скоринга измерена на 14 вакансиях — этого мало.** Baseline снят:
  при пороге 0.6 precision 1.000, recall 0.750, ложных срабатываний нет. Но
  разметку делал агент, а не человек, и на четырнадцати примерах интервал
  precision тянется от 0.44 до 1.00. Подробности и оговорки —
  [docs/EVAL-BASELINE.md](docs/EVAL-BASELINE.md).
- **Нет мониторинга доступности и SLA.** Проценты uptime в отчётах не
  публикуются, потому что измерять их нечем.
- **Бесплатные модели отвечают нестабильно.** На живых прогонах 24.09.2026 часть
  вызовов вернула рассуждения вместо JSON: из трёх вакансий то две доходили до
  черновика, то ни одной. Клиент разбирает ответ и один раз переспрашивает, а
  вакансию, которую так и не удалось разобрать, конвейер пропускает и идёт
  дальше — но стабильной такую работу назвать нельзя. Для предсказуемости нужен
  платный провайдер или Groq/Cerebras, а не бесплатный тариф OpenRouter.
- **Проверка на выдумки не гарантия.** Она сама работает на модели, поэтому
  снижает риск, но не устраняет его: 24.09.2026 она пропустила черновик с
  приписанным нам опытом и поймала его только после правки промпта. Настоящая
  гарантия — гейт подтверждения человеком.
- **Профиль отправителя и ICP — заготовки.** С ними проверка на выдумки
  отклоняет почти каждый черновик: генератору не на что опереться. Конвейер
  предупреждает об этом в логе, но заполнить профиль должен человек.

## Документация

Полный указатель — [docs/README.md](docs/README.md). Самое нужное:

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — слои, поток данных, схема, безопасность
- [docs/CONCEPT.md](docs/CONCEPT.md) — зачем это и для кого
- [docs/DEMO.md](docs/DEMO.md) — демо-сценарий
- [docs/DEPLOY.md](docs/DEPLOY.md) — развёртывание
- [docs/PROJECT-STATUS.md](docs/PROJECT-STATUS.md) — что работает, чего нет
- [CONTRIBUTING.md](CONTRIBUTING.md) — как вносить изменения
- [SECURITY.md](SECURITY.md) — как сообщить об уязвимости
- [CHANGELOG.md](CHANGELOG.md) — что менялось

## Лицензия

MIT — см. [LICENSE](LICENSE).

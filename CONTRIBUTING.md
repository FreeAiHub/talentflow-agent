# 🤝 Contributing to TalentFlow Agent

Спасибо за интерес к проекту TalentFlow Agent! Мы рады любому вкладу — от исправления опечаток до реализации новых фич.

## 📋 Содержание

- [Code of Conduct](#code-of-conduct)
- [Как я могу помочь?](#как-я-могу-помочь)
- [Процесс разработки](#процесс-разработки)
- [Стандарты кода](#стандарты-кода)
- [Процесс Pull Request](#процесс-pull-request)
- [Коммит-сообщения](#коммит-сообщения)
- [Тестирование](#тестирование)

---

## 📜 Code of Conduct

Мы следуем стандартному [Contributor Covenant Code of Conduct](https://www.contributor-covenant.org/version/2/1/code_of_conduct/). Пожалуйста, ознакомьтесь с ним перед участием.

**Основные принципы:**
- Уважайте других участников
- Будьте открыты к конструктивной критике
- Сосредоточьтесь на том, что лучше для сообщества
- Проявляйте эмпатию к другим участникам

---

## 💡 Как я могу помочь?

### 🐛 Сообщить о баге

Нашли баг? Создайте [Issue](https://github.com/FreeAiHub/talentflow-agent/issues/new?template=bug_report.md) с:
- Подробным описанием проблемы
- Шагами для воспроизведения
- Ожидаемым и фактическим поведением
- Версией Python (`uv run python --version`)
- Логами (если возможно)

### ✨ Предложить фичу

Есть идея улучшения? Создайте [Issue](https://github.com/FreeAiHub/talentflow-agent/issues/new) с:
- Четким описанием проблемы, которую решает фича
- Предлагаемым решением
- Альтернативными подходами (опционально)

> Примечание: готового шаблона «Feature Request» в репозитории нет
> (в `.github/ISSUE_TEMPLATE/` лежит только `bug_report.md`), поэтому фичи
> заводятся через общую форму Issue.

### 📝 Улучшить документацию

Документация никогда не бывает идеальной! Вы можете:
- Исправить опечатки и грамматические ошибки
- Добавить примеры использования
- Улучшить объяснения
- Перевести на другие языки

### 🔧 Написать код

Готовы писать код? Отлично! Проверьте:
- [Good First Issues](https://github.com/FreeAiHub/talentflow-agent/labels/good%20first%20issue) — для новичков
- [Help Wanted](https://github.com/FreeAiHub/talentflow-agent/labels/help%20wanted) — задачи, где нужна помощь
- [Linear Project](https://linear.app/talentflowhub/project/talentflow-bb78fd48809f) — дорожная карта проекта

---

## 📏 Документация: утверждение без доказательства не публикуется

Любое утверждение о том, что система делает, поддерживает или позволяет,
сопровождается одним из трёх:

- **путём к файлу** — `src/talentflow/parsers/djinni.py`;
- **именем теста** — `tests/test_djinni_parser.py`;
- **командой и её выводом** — `uv run pytest -q` → `297 passed` (замер: 24.09.2026).

Чего делать нельзя:

- **Числа без замера.** «25+ моделей», «10 000+ откликов», «99.9% uptime» —
  ни одно из них репозиторием не подтверждается. Если число получено замером,
  рядом стоит команда и дата; если не получено — числа нет.
- **Технологии из планов в описании настоящего.** Redis, Celery, Grafana,
  Next.js в этом репозитории не используются. Планируемое живёт в разделе
  «Планы» и помечается словом «планируется».
- **Оценочные усилители.** «production-ready», «enterprise», «мировой уровень»
  не добавляют доверия, а отнимают его: технический читатель проверяет первое
  же такое слово.

Проверка перед коммитом:

```bash
grep -rniE "production-ready|enterprise|uptime|SOC2|99\.[0-9]|seamless" \
  README.md README_EN.md docs/*.md
```

Совпадение не всегда ошибка: «проценты uptime не публикуются, потому что не
измеряются» — честная фраза. Ошибка — когда утверждение выдаётся за факт.

**Почему правило появилось.** README этого проекта месяцами описывал продукт,
которого не было: документации было больше, чем кода.

---

## 🛠️ Процесс разработки

### 1. Форкните репозиторий

```bash
# Нажмите Fork на GitHub, затем:
git clone https://github.com/YOUR-USERNAME/talentflow-agent.git
cd talentflow-agent
git remote add upstream https://github.com/FreeAiHub/talentflow-agent.git
```

### 2. Настройте окружение

Проект использует [uv](https://docs.astral.sh/uv/) — один инструмент вместо
`venv` + `pip`. Зависимости зафиксированы в `uv.lock`.

```bash
# Установите uv (один раз): https://docs.astral.sh/uv/getting-started/installation/

# Создайте .venv и установите проект вместе с dev-зависимостями (pytest, ruff, mypy)
uv sync

# Скопируйте .env — все переменные с префиксом TALENTFLOW_, см. src/talentflow/config.py
cp .env.example .env
# Отредактируйте .env с вашими API ключами (.env в git не попадает)
```

Команды запускайте через `uv run ...` — активировать окружение вручную не нужно.
Перед коммитом прогоните то же, что запускает CI (`.github/workflows/ci.yml`):

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
uv run mypy
```

### 3. Создайте ветку

```bash
# Синхронизируйтесь с upstream
git fetch upstream
git checkout main
git merge upstream/main

# Создайте feature-ветку
git checkout -b feature/amazing-feature
# или
git checkout -b fix/bug-description
```

### 4. Пишите код

- Следуйте нашим [стандартам кода](#стандарты-кода)
- Пишите тесты для новой функциональности
- Обновите документацию при необходимости
- Убедитесь, что все тесты проходят

### 5. Коммитьте изменения

```bash
git add .
git commit -m "feat: add amazing feature"
# Следуйте Conventional Commits (см. ниже)
```

### 6. Отправьте в GitHub

```bash
git push origin feature/amazing-feature
```

### 7. Создайте Pull Request

- Перейдите на GitHub и создайте PR
- Заполните шаблон PR
- Дождитесь code review

---

## 📐 Стандарты кода

### Python

#### Форматирование и линтинг

Мы используем **Ruff** — он заменяет Black, isort и flake8 сразу. Настройки
живут в `pyproject.toml`, отдельные конфиги не нужны.

```bash
# Форматирование
uv run ruff format .

# Проверка форматирования без правок (то же гоняет CI)
uv run ruff format --check .

# Линтинг
uv run ruff check .

# Линтинг с автоисправлением того, что исправимо
uv run ruff check --fix .

# Типы
uv run mypy
```

Все четыре команды должны проходить до коммита — ровно их запускает
`.github/workflows/ci.yml`.

#### Type Hints

Обязательно используйте type hints. Реальные доменные типы живут в
`talentflow.models` — `Vacancy`, `ScoredVacancy`, `ApplicationResponse`:

```python
from talentflow.models import Vacancy

# ✅ Хорошо
def parse_vacancy(vacancy: Vacancy) -> dict[str, str]:
    """Pack a vacancy into an outgoing payload."""
    return {"id": vacancy.id, "title": vacancy.title}

# ❌ Плохо
def parse_vacancy(vacancy):
    return {}  # тип утерян, IDE и mypy не помогут
```

Какие доменные типы реально существуют — смотрите `uv run python -c
"import talentflow.models"` или grep по `src/talentflow/models.py`.

#### Docstrings

Используйте Google-style docstrings:

```python
from talentflow.models import ScoredVacancy

def score_vacancy(vacancy: Vacancy) -> ScoredVacancy:
    """
    Score a vacancy.

    Args:
        vacancy: The vacancy to score.

    Returns:
        A vacancy with a ``score`` in [0, 1], a ``reasons`` list, or defaults.

    Raises:
        ValueError: If vacancy data is invalid.
    """
    ...
```

#### Структура кода

Импортируйте из пакета `talentflow` (в каталоге `src/`), а не по плоским путям
`src.database` / `src.utils` / `src.api` — их в проекте нет, `grep -rn`
не найдёт их ни в одном файле.

```python
"""Модуль-пример: порядок импортов и констант в файле проекта."""

# Стандартная библиотека
import logging

# Сторонние
from sqlalchemy import select

# Проект — всегда с корнем `talentflow.` и с публичного пути пакета, а не из
# внутреннего подмодуля (`storage.db` — внутренний; импортируйте из `storage`).
from talentflow.models import Vacancy
from talentflow.storage import get_session

# Логгер — как принято в проекте, через logging.getLogger; модуля
# `talentflow.utils.logger` не существует.
logger = logging.getLogger(__name__)

# Константы
MAX_RETRIES = 3
TIMEOUT = 30
```

Проверить, что импорт корректен, можно до написания кода:

```bash
uv run python -c "import talentflow.models, talentflow.parsers.djinni"
```

### JavaScript/TypeScript

В этом репозитории нет JavaScript/TypeScript: `git ls-files` не показывает ни
одного `.js`/`.ts`-файла, нет `package.json`, и ни CI не вызывает `npm`, ни
документация на него не ссылается. Весь код — Python. Прежний раздел про
Prettier/ESLint описывал фронтенд, которого в проекте нет, поэтому удалён.

---

## 🔄 Процесс Pull Request

### Чеклист перед созданием PR

- [ ] Код следует нашим стандартам
- [ ] Все тесты проходят (`pytest tests/`)
- [ ] Добавлены новые тесты для новой функциональности
- [ ] Документация обновлена
- [ ] Нет конфликтов с `main` веткой
- [ ] Коммиты следуют Conventional Commits

### Шаблон описания PR

```markdown
## Описание
Краткое описание изменений

## Тип изменения
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Тестирование
Опишите тесты, которые вы запустили

## Чеклист
- [ ] Мой код следует стилю проекта
- [ ] Я проверил свои изменения
- [ ] Я прокомментировал сложные части
- [ ] Я обновил документацию
- [ ] Мои изменения не создают warnings
- [ ] Добавлены тесты
- [ ] Все новые и существующие тесты проходят
```

### Code Review

Ожидайте:
- Конструктивные комментарии в течение 48 часов
- Возможные запросы на изменения
- Автоматические проверки CI/CD

---

## 📝 Коммит-сообщения

Мы следуем [Conventional Commits](https://www.conventionalcommits.org/):

### Формат

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- `feat`: Новая функциональность
- `fix`: Исправление бага
- `docs`: Изменения в документации
- `style`: Форматирование (не влияет на код)
- `refactor`: Рефакторинг кода
- `perf`: Улучшение производительности
- `test`: Добавление тестов
- `chore`: Изменения в сборке/CI
- `ci`: Изменения в CI/CD
- `build`: Изменения в зависимостях

### Примеры

```bash
# Новая фича
git commit -m "feat(parser): add Djinni.co parser"

# Исправление бага
git commit -m "fix(api): handle null vacancy data"

# Документация
git commit -m "docs: update installation guide"

# С body и footer
git commit -m "feat(ai): add Claude 3.5 integration

Add Claude 3.5 Sonnet model for vacancy analysis
Update flowise workflows

Closes #123"
```

---

## 🧪 Тестирование

### Запуск тестов

Тесты лежат в `tests/` (настроено через `[tool.pytest.ini_options]` в `pyproject.toml`).

```bash
# Все тесты
uv run pytest

# Конкретный файл
uv run pytest tests/test_health.py

# С verbose
uv run pytest -v
```

### Написание тестов

#### Unit тесты

Пишите тесты в стиле `tests/test_djinni_parser.py`. Парсеры — асинхронные, их
публичный метод — `collect()`, возвращающий `list[Vacancy]`; метода `parse()`
нет, как нет и сети в тестах: вместо неё — `httpx.MockTransport`.

```python
from pathlib import Path

import httpx

from talentflow.models import Vacancy
from talentflow.parsers.djinni import DjinniParser

FIXTURE = Path(__file__).parent / "fixtures" / "djinni_jobs_page1.html"


def _client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_collect_parses_a_recorded_listing_page() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=FIXTURE.read_text(encoding="utf-8"))

    parser = DjinniParser(client=_client(handler), request_delay=0, backoff_base=0)
    vacancies = await parser.collect()

    assert isinstance(vacancies, list)
    assert all(isinstance(v, Vacancy) for v in vacancies)
    assert vacancies[0].title  # непустой заголовок первой вакансии
```

Полный эталон — `tests/test_djinni_parser.py`: там 15+ тестов на сбор
(пагинация, дедупликация, rate-limit, обрывы сети) с использованием записанной
HTML-страницы из `tests/fixtures/`.

#### Integration тесты

API тестируется через `httpx.AsyncClient` с `ASGITransport` и фикстуру
`api_client` из `tests/conftest.py`, а не через `TestClient` — тело теста и сессия
БД живут в одном event loop. Реальные маршруты: `GET /health`, `GET
/api/v1/vacancies`, `GET /api/v1/applications`, `POST
/api/v1/applications/{id}/approve|reject`, `GET /api/v1/stats`, вебхуки
`POST /webhooks/telegram` и `POST /webhooks/vapi`. Эндпоинта `POST
/api/v1/vacancies` нет.

```python
import httpx


async def test_health_returns_ok_and_version(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0"}
```

Это дословно `tests/test_health.py`; сигнатуры остальных маршрутов смотрите в
`src/talentflow/api/main.py` и их тестах в `tests/test_storage.py`.

### Покрытие тестами

Покрытие в репозитории **не измеряется автоматически**: `pytest-cov` нет ни в
зависимостях (`pyproject.toml`, `uv.lock`), ни в CI. Требования «80% для нового
кода» и «100% критичных путей» как измеримые правила здесь не действуют — их
нечем проверить.

Что действует на практике:

- **Каждая новая функциональность получает тесты.** Это проверяет CI —
  ревьювер отклонит PR без теста на новое поведение.
- **Закрывайте ветки кода, которые реально можете закрыть.** Полезный ориентир —
  запустить `uv run pytest --cov=... --cov-report=term` локально, если у вас
  установлен `pytest-cov`, но результат нигде не хранится и не гейтит PR.

Решение о добавлении измерителя (`pytest-cov` и шаг в CI) — отдельное
(владелец), в этой задаче зависимости не менялись.

---

## 🎨 Дополнительные рекомендации

### Работа с Linear

Если у вас есть доступ к [Linear Project](https://linear.app/talentflowhub/project/talentflow-bb78fd48809f):

1. Выберите задачу из бэклога
2. Переместите в "In Progress"
3. Создайте ветку с номером задачи: `feature/TAL-123-description`
4. В PR укажите: `Fixes TAL-123`

### AI-Assisted Development

Мы активно используем AI инструменты:
- **Cursor IDE** для ускорения разработки
- **Claude/GPT** для генерации boilerplate
- **GitHub Copilot** для автодополнения

Не стесняйтесь использовать их, но всегда проверяйте сгенерированный код!

### Работа с документацией

- Документация в `docs/`
- Используйте Markdown
- Добавляйте диаграммы (Mermaid, PNG)
- Обновляйте CHANGELOG.md

---

## 📞 Получить помощь

Есть вопросы? Мы здесь, чтобы помочь!

- 💬 [GitHub Discussions](https://github.com/FreeAiHub/talentflow-agent/discussions)
- 🐛 [Issues](https://github.com/FreeAiHub/talentflow-agent/issues)
- 📋 [Linear](https://linear.app/talentflowhub/project/talentflow-bb78fd48809f)

---

## 🙏 Благодарности

Спасибо всем контрибьюторам за вклад в проект!

[![Contributors](https://contrib.rocks/image?repo=FreeAiHub/talentflow-agent)](https://github.com/FreeAiHub/talentflow-agent/graphs/contributors)

---

**Happy Coding! 🚀**

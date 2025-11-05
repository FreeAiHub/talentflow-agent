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
- Версией Python/Node.js
- Логами (если возможно)

### ✨ Предложить фичу

Есть идея улучшения? Создайте [Feature Request](https://github.com/FreeAiHub/talentflow-agent/issues/new?template=feature_request.md) с:
- Четким описанием проблемы, которую решает фича
- Предлагаемым решением
- Альтернативными подходами (опционально)

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

## 🛠️ Процесс разработки

### 1. Форкните репозиторий

```bash
# Нажмите Fork на GitHub, затем:
git clone https://github.com/YOUR-USERNAME/talentflow-agent.git
cd talentflow-agent
git remote add upstream https://github.com/FreeAiHub/talentflow-agent.git
```

### 2. Настройте окружение

```bash
# Создайте виртуальное окружение
python -m venv venv
source venv/bin/activate  # На Windows: venv\Scripts\activate

# Установите зависимости
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Установите pre-commit hooks
pre-commit install

# Скопируйте .env
cp .env.example .env
# Отредактируйте .env с вашими API ключами
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

#### Форматирование

Мы используем **Black** и **isort**:

```bash
# Форматирование
black src/ tests/
isort src/ tests/

# Проверка
flake8 src/ tests/
mypy src/
```

#### Type Hints

Обязательно используйте type hints:

```python
# ✅ Хорошо
def parse_vacancy(url: str) -> dict[str, Any]:
    """Parse vacancy from URL."""
    pass

# ❌ Плохо
def parse_vacancy(url):
    pass
```

#### Docstrings

Используйте Google-style docstrings:

```python
def analyze_vacancy(vacancy: dict[str, Any]) -> AnalysisResult:
    """
    Analyze vacancy using AI.

    Args:
        vacancy: Vacancy data dictionary

    Returns:
        Analysis result with scores and insights

    Raises:
        ValueError: If vacancy data is invalid
    """
    pass
```

#### Структура кода

```python
# Импорты
import os
from typing import Any

from fastapi import FastAPI
from sqlalchemy import select

from src.database.models import Vacancy
from src.utils.logger import logger

# Константы
MAX_RETRIES = 3
TIMEOUT = 30

# Классы и функции
class VacancyParser:
    """Vacancy parser implementation."""
    pass
```

### JavaScript/TypeScript

#### Форматирование

Мы используем **Prettier** и **ESLint**:

```bash
# Форматирование
npm run format

# Проверка
npm run lint
```

#### Стиль

```typescript
// ✅ Хорошо
interface VacancyData {
  id: string;
  title: string;
  company: string;
}

const parseVacancy = async (url: string): Promise<VacancyData> => {
  // ...
};

// ❌ Плохо
const parseVacancy = (url) => {
  // ...
};
```

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

```bash
# Все тесты
pytest

# С coverage
pytest --cov=src --cov-report=html

# Только unit тесты
pytest tests/unit/

# Только integration тесты
pytest tests/integration/

# Конкретный файл
pytest tests/unit/test_parsers.py

# С verbose
pytest -v
```

### Написание тестов

#### Unit тесты

```python
import pytest
from src.parsers.djinni import DjinniParser

def test_parse_vacancy_success():
    """Test successful vacancy parsing."""
    parser = DjinniParser()
    result = parser.parse("https://djinni.co/jobs/12345")
    
    assert result["title"] is not None
    assert result["company"] is not None
    assert "salary" in result

def test_parse_vacancy_invalid_url():
    """Test parsing with invalid URL."""
    parser = DjinniParser()
    
    with pytest.raises(ValueError):
        parser.parse("invalid-url")
```

#### Integration тесты

```python
import pytest
from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)

def test_create_vacancy():
    """Test vacancy creation endpoint."""
    response = client.post(
        "/api/v1/vacancies",
        json={
            "url": "https://djinni.co/jobs/12345",
            "source": "djinni"
        }
    )
    
    assert response.status_code == 201
    assert "id" in response.json()
```

### Coverage Requirements

- Минимум 80% покрытия для нового кода
- Критичные пути должны быть покрыты на 100%

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

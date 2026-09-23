# Руководство по участию в проекте TalentFlow Agent

Спасибо за интерес к проекту! Мы приветствуем любой вклад в развитие TalentFlow Agent.

## 📋 Содержание

- [Кодекс поведения](#кодекс-поведения)
- [Как начать](#как-начать)
- [Процесс контрибуции](#процесс-контрибуции)
- [Стиль кода](#стиль-кода)
- [Тестирование](#тестирование)
- [Коммиты и Pull Requests](#коммиты-и-pull-requests)
- [Баг-репорты](#баг-репорты)
- [Предложения новых функций](#предложения-новых-функций)

## 🤝 Кодекс поведения

Участие в проекте регулируется принципами взаимного уважения и конструктивного сотрудничества:

- Будьте доброжелательны и терпимы
- Уважайте различные точки зрения и опыт
- Конструктивно воспринимайте критику
- Фокусируйтесь на том, что лучше для сообщества
- Проявляйте эмпатию к другим участникам

## 🚀 Как начать

### 1. Форкните репозиторий

```bash
git clone https://github.com/ваш-username/talentflow-agent.git
cd talentflow-agent
```

### 2. Настройте окружение

```bash
# Создайте .venv и установите зависимости (включая dev: pytest, ruff, mypy)
uv sync

# Скопируйте .env и заполните ключи
cp .env.example .env
```

Команды запускайте через `uv run ...` — активировать окружение не нужно.
Проект использует [uv](https://docs.astral.sh/uv/), зависимости зафиксированы
в `uv.lock`.
```

### 3. Создайте ветку для работы

```bash
git checkout -b feature/имя-функции
# или
git checkout -b fix/описание-бага
```

## 🔄 Процесс контрибуции

1. **Найдите или создайте Issue**
   - Проверьте существующие Issues
   - Создайте новый Issue для обсуждения изменений
   - Дождитесь одобрения перед началом работы

2. **Разработка**
   - Пишите чистый и понятный код
   - Следуйте стилю кода проекта
   - Добавляйте комментарии для сложных участков
   - Обновляйте документацию при необходимости

3. **Тестирование**
   - Напишите тесты для нового функционала
   - Убедитесь, что все тесты проходят
   - Проверьте покрытие кода

4. **Коммит и Push**
   - Следуйте формату Conventional Commits
   - Делайте атомарные коммиты
   - Push в свой форк

5. **Pull Request**
   - Создайте PR в ветку `develop`
   - Заполните шаблон PR
   - Ответьте на комментарии ревьюеров
   - Внесите необходимые исправления

## 💅 Стиль кода

### Python

Мы следуем [PEP 8](https://www.python.org/dev/peps/pep-0008/) с некоторыми дополнениями:

```python
# Импорты группируются и сортируются
import os
import sys

from typing import List, Optional

import pandas as pd
import numpy as np

from src.core import config
from src.agents import TalentScout

# Максимальная длина строки: 100 символов
# Используйте type hints
def process_candidate(
    candidate_id: int,
    filters: Optional[List[str]] = None
) -> dict:
    """Process candidate data.
    
    Args:
        candidate_id: Unique identifier for the candidate
        filters: Optional list of filters to apply
        
    Returns:
        Processed candidate data as dictionary
    """
    pass

# Используйте f-strings для форматирования
message = f"Processing candidate {candidate_id}"

# Классы именуются в PascalCase
class CandidateProcessor:
    def __init__(self, config: dict):
        self.config = config
```

### Форматирование

Используйте **Ruff** — он заменяет Black, isort и flake8 сразу:

```bash
# Форматирование
uv run ruff format .

# Линтинг (с --fix для автоисправлений)
uv run ruff check .

# Проверка типов
uv run mypy
```

## 🧪 Тестирование

### Запуск тестов

```bash
# Все тесты
pytest

# С покрытием
pytest --cov=src --cov-report=html

# Конкретный файл
pytest tests/unit/test_talent_scout.py

# С подробным выводом
pytest -v
```

### Написание тестов

```python
import pytest
from src.agents import TalentScout


class TestTalentScout:
    @pytest.fixture
    def scout(self):
        return TalentScout(config={"api_key": "test"})
    
    def test_search_candidates(self, scout):
        """Test candidate search functionality."""
        results = scout.search(query="Python Developer")
        assert len(results) > 0
        assert "name" in results[0]
    
    def test_invalid_query(self, scout):
        """Test handling of invalid queries."""
        with pytest.raises(ValueError):
            scout.search(query="")
```

### Требования к тестам

- Покрытие кода > 80%
- Unit тесты для всех публичных методов
- Integration тесты для критических путей
- Mock внешние зависимости
- Используйте fixtures для повторяющихся настроек

## 📝 Коммиты и Pull Requests

### Формат коммитов (Conventional Commits)

```
<тип>(<область>): <краткое описание>

<подробное описание (опционально)>

<footer (опционально)>
```

**Типы коммитов:**
- `feat`: новая функциональность
- `fix`: исправление бага
- `docs`: изменения в документации
- `style`: форматирование, пропущенные точки с запятой и т.д.
- `refactor`: рефакторинг кода
- `test`: добавление или изменение тестов
- `chore`: обновление задач сборки, настроек и т.д.
- `perf`: улучшение производительности

**Примеры:**

```bash
feat(agents): add interview scheduling functionality

fix(database): resolve connection timeout issue

docs(readme): update installation instructions

test(scout): add tests for candidate filtering
```

### Pull Request шаблон

```markdown
## Описание
Краткое описание изменений

## Тип изменений
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Checklist
- [ ] Код следует стилю проекта
- [ ] Проведен self-review кода
- [ ] Добавлены комментарии для сложных участков
- [ ] Обновлена документация
- [ ] Изменения не генерируют новых предупреждений
- [ ] Добавлены тесты
- [ ] Все тесты проходят успешно
- [ ] Зависимые изменения были объединены

## Связанные Issues
Fixes #123
Related to #456
```

## 🐛 Баг-репорты

При создании баг-репорта используйте шаблон Issue:

```markdown
**Описание бага**
Четкое и краткое описание проблемы

**Шаги для воспроизведения**
1. Перейдите к '...'
2. Кликните на '...'
3. Прокрутите до '...'
4. Наблюдайте ошибку

**Ожидаемое поведение**
Описание того, что должно было произойти

**Скриншоты**
Если применимо, добавьте скриншоты

**Окружение:**
- OS: [e.g. Ubuntu 20.04]
- Python версия: [e.g. 3.9.7]
- Версия проекта: [e.g. 0.1.0]

**Дополнительный контекст**
Любая другая информация о проблеме
```

## 💡 Предложения новых функций

Для предложения новой функциональности:

```markdown
**Проблема**
Описание проблемы, которую решает функция

**Предлагаемое решение**
Четкое описание того, что вы хотите добавить

**Альтернативы**
Описание рассмотренных альтернативных решений

**Дополнительный контекст**
Любая другая информация или скриншоты
```

## 📚 Дополнительные ресурсы

- [Python PEP 8](https://www.python.org/dev/peps/pep-0008/)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [Semantic Versioning](https://semver.org/)
- [Git Flow](https://nvie.com/posts/a-successful-git-branching-model/)

## ❓ Вопросы

Если у вас есть вопросы:
- Создайте Issue с тегом `question`
- Проверьте [Wiki](https://github.com/FreeAiHub/talentflow-agent/wiki)
- Обсудите в [Discussions](https://github.com/FreeAiHub/talentflow-agent/discussions)

## 📜 Лицензия

Участвуя в этом проекте, вы соглашаетесь с тем, что ваш вклад будет лицензирован под [MIT License](../LICENSE).

---

**Спасибо за ваш вклад в TalentFlow Agent! 🎉**

# 🚀 TalentFlow Agent

<div align="center">

![Version](https://img.shields.io/badge/version-0.1.0--pre--mvp-blue)
![Python](https://img.shields.io/badge/python-3.11+-green)
![License](https://img.shields.io/badge/license-MIT-blue)
![Status](https://img.shields.io/badge/status-in--development-yellow)

**AI-Платформа для автоматизации лидогенерации через интеллектуальный анализ вакансий**

[Документация](./docs/PROJECT-STRUCTURE.md) · [Linear Project](https://linear.app/talentflowhub/project/talentflow-bb78fd48809f) · [Мастер-план](./data/TalentFlow-Agent-Master-Plan.md)

</div>

---

## 📖 О проекте

**TalentFlow Agent** — это open-source AI-агент для автоматизации лидогенерации в сфере аутстаффинга и рекрутинга. Система анализирует вакансии с job-порталов (Djinni.co, Work.ua, LinkedIn) и генерирует персонализированные коммерческие предложения с высокой конверсией.

### 🎯 Ключевые возможности

- **🔍 Интеллектуальный парсинг** — Автоматизированный сбор вакансий с нескольких источников
- **🤖 AI-анализ** — Глубокий анализ требований и болей компании через Claude 4.5 Sonnet
- **✨ Генерация предложений** — Персонализированные отклики с высокой конверсией
- **📊 Lead Scoring** — Автоматическая оценка качества лидов
- **📈 Analytics** — Dashboard с метриками и конверсиями
- **🔄 Интеграции** — Calendly, CRM, Telegram, Email

---

## 🏗️ Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                    TalentFlow Agent                          │
│              AI-Платформа для Lead Generation                │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Parsers    │────▶│  AI Engine   │────▶│   Output     │
│              │     │  (Flowise)   │     │              │
│ • Djinni.co  │     │              │     │ • Leads DB   │
│ • Work.ua    │     │ • Analyzer   │     │ • Dashboard  │
│ • LinkedIn   │     │ • Generator  │     │ • CRM        │
│ • JobSpy     │     │ • Scorer     │     │ • Linear     │
└──────────────┘     └──────────────┘     └──────────────┘
```

**Детальная документация:**
- 📐 [Глобальная архитектура](./docs/GLOBAL-ARCHITECTURE.md) — полная техническая документация
- 🔄 [Flowise интеграция](./docs/FLOWISE-INTEGRATION.md) — AI-оркестрация и workflows
- 🎯 [Презентация для клиента](./docs/CLIENT-PRESENTATION.md) — бизнес-ценность и ROI
- 📁 [Структура проекта](./docs/PROJECT-STRUCTURE.md) — организация кодовой базы

---

## 🚀 Быстрый старт

### Требования

- Python 3.11+
- Node.js 18+ (для MCP сервера)
- Docker & Docker Compose
- PostgreSQL 15+
- Redis 7+

### Установка

```bash
# Клонировать репозиторий
git clone https://github.com/FreeAiHub/talentflow-agent.git
cd talentflow-agent

# Установить зависимости Python
pip install -r requirements.txt

# Установить зависимости Node.js (MCP)
npm install

# Настроить окружение
cp .env.example .env
# Отредактируйте .env с вашими API ключами

# Запустить через Docker
docker-compose up -d

# Запустить миграции
python scripts/migrate.py
```

### API Ключи

Вам понадобятся:
- **LINEAR_API_KEY** — для интеграции с Linear ([получить](https://linear.app/settings/api))
- **OPENAI_API_KEY** — для GPT моделей
- **ANTHROPIC_API_KEY** — для Claude 3.5 Sonnet
- **FLOWISE_API_KEY** — для Flowise AI оркестрации

---

## 📁 Структура проекта

```
talentflow-agent/
├── src/
│   ├── parsers/         # Парсеры вакансий (Djinni, Work.ua, LinkedIn)
│   ├── agents/          # AI агенты (анализ, генерация, scoring)
│   ├── services/        # Бизнес-логика и интеграции
│   │   ├── flowise_client.py    # Flowise API клиент
│   │   ├── ai_engine.py         # AI-движок
│   │   └── integrations/        # Внешние сервисы
│   ├── api/             # FastAPI REST API
│   ├── database/        # SQLAlchemy модели и CRUD
│   ├── mcp-server/      # Linear MCP интеграция
│   └── utils/           # Утилиты и хелперы
├── workflows/
│   ├── flowise/         # Flowise AI workflows
│   │   ├── analyzer.json        # Workflow анализа вакансий
│   │   ├── generator.json       # Workflow генерации откликов
│   │   └── scorer.json          # Workflow оценки лидов
│   └── n8n/             # n8n автоматизация
├── tests/               # Unit, Integration, E2E тесты
├── docs/                # 📚 Подробная документация
│   ├── GLOBAL-ARCHITECTURE.md   # Архитектура системы
│   ├── FLOWISE-INTEGRATION.md   # Flowise workflows
│   ├── CLIENT-PRESENTATION.md   # Презентация проекта
│   └── PROJECT-STRUCTURE.md     # Структура проекта
└── docker/              # Docker конфигурация
```

**[Детальная структура →](./docs/PROJECT-STRUCTURE.md) | [Архитектура →](./docs/GLOBAL-ARCHITECTURE.md)**

---

## ✅ Статус разработки

### Phase 0: Подготовка (Текущая фаза)
- [x] Настройка Linear MCP сервера
- [x] Создание структуры проекта
- [x] 6 Milestones и 13 задач созданы
- [ ] Анализ структуры Djinni.co
- [ ] Исследование болей пользователей
- [ ] Финализация технической спецификации

### Phase 1: MVP (В работе)
- [ ] Базовая инфраструктура
- [ ] Парсер Djinni.co
- [ ] Flowise чатфлоу для анализа вакансий
- [ ] Генератор откликов
- [ ] База данных и REST API

**[Полный roadmap →](https://linear.app/talentflowhub/project/talentflow-bb78fd48809f)**

---

## 🛠️ Технологический стек

### Backend
- **Python 3.11+** — Core language
- **FastAPI** — Modern async API framework
- **PostgreSQL** — Primary database
- **Redis** — Cache & queues
- **SQLAlchemy 2.0** — ORM
- **Alembic** — DB migrations

### AI/ML
- **Claude 3.5 Sonnet** — Primary LLM (Anthropic)
- **GPT-4o-mini** — Fallback LLM (OpenAI)
- **Flowise AI** — Visual AI workflow builder
- **Langchain** — LLM orchestration
- **Pinecone** — Vector database

### Frontend (Планируется)
- **Next.js 14** — React framework
- **TypeScript** — Type safety
- **Tailwind CSS** — Styling
- **Shadcn/ui** — Component library
- **Echarts** — Data visualization

### DevOps
- **Docker** — Containerization
- **GitHub Actions** — CI/CD
- **Prometheus** — Monitoring
- **OpenTelemetry** — Tracing

---

## 🎯 Use Cases

### 1. Аутстаф-компании
Автоматизируйте поиск клиентов через анализ вакансий и генерацию персонализированных предложений.

### 2. Рекрутеры-фрилансеры
Находите релевантные вакансии и создавайте качественные отклики в 10x меньше времени.

### 3. HR-агентства
Масштабируйте лидогенерацию без увеличения команды.

---

## 📊 Протестированные инструменты

### ✅ Linear MCP Server

**Статус:** Полностью настроен и работает

**Возможности:**
- Управление задачами из Cline AI
- Создание и поиск issues
- Работа с комментариями и milestones
- Автоматизация workflow

**Созданная структура:**
- 6 Milestones (Phase 0-5)
- 38 задач с детальным описанием
- Учебная задача с примерами

### 🔄 В разработке

- **Flowise AI Workflows** — визуальные AI-цепочки (см. [документацию](./docs/FLOWISE-INTEGRATION.md))
  - ✅ Analyzer Workflow — извлечение KPIs и болей
  - 🚧 Generator Workflow — персонализированные отклики
  - 🚧 Scorer Workflow — приоритизация лидов
- **Djinni.co Parser** — парсинг украинских вакансий
- **Work.ua Parser** — расширение на дополнительный портал
- **LinkedIn Parser** — международные вакансии (интеграция JobSpy)

---

## 📖 Документация

### 🎯 Для бизнеса и клиентов
- **[Презентация проекта](./docs/CLIENT-PRESENTATION.md)** — ценность, ROI, use cases
- **[Мастер-план](./data/TalentFlow-Agent-Master-Plan.md)** — полный план развития

### 🏗️ Для разработчиков
- **[Глобальная архитектура](./docs/GLOBAL-ARCHITECTURE.md)** — детальная техническая архитектура
- **[Flowise интеграция](./docs/FLOWISE-INTEGRATION.md)** — AI workflows и оркестрация
- **[Структура проекта](./docs/PROJECT-STRUCTURE.md)** — организация кодовой базы
- **[API Reference](./docs/API-REFERENCE.md)** — документация API (в разработке)

### 🔧 Инструменты и гайды
- **[Linear Guide](./data/Linea/Linear-Practical-Guide.md)** — работа с task management
- **[Contributing](./CONTRIBUTING.md)** — как внести вклад в проект

---

## 🤝 Контрибьюция

Мы приветствуем вклад от сообщества! Вот как вы можете помочь:

1. 🐛 **Репортить баги** через [Issues](https://github.com/FreeAiHub/talentflow-agent/issues)
2. 💡 **Предлагать фичи** через [Discussions](https://github.com/FreeAiHub/talentflow-agent/discussions)
3. 📝 **Улучшать документацию**
4. 🔧 **Создавать Pull Requests**

**[Contributing Guide →](./CONTRIBUTING.md)** (скоро)

---

## 🗺️ Roadmap

### Q4 2025 (Ноябрь-Декабрь)
- ✅ Настройка инфраструктуры
- ⏳ MVP Djinni.co парсер
- ⏳ Flowise AI интеграция
- ⏳ Базовый dashboard

### Q1 2026 (Январь-Март)
- [ ] Work.ua и LinkedIn парсеры
- [ ] Advanced analytics
- [ ] Landing page
- [ ] Product Hunt launch

### Q2 2026 (Апрель-Июнь)
- [ ] SaaS монетизация
- [ ] Mobile app
- [ ] Multi-language support
- [ ] Enterprise features

**[Детальный roadmap в Linear →](https://linear.app/talentflowhub/project/talentflow-bb78fd48809f)**

---

## 📞 Контакты и Связь

- **GitHub:** [FreeAiHub/talentflow-agent](https://github.com/FreeAiHub/talentflow-agent)
- **Linear:** [TalentFlow Project](https://linear.app/talentflowhub/project/talentflow-bb78fd48809f)
- **Issues:** [GitHub Issues](https://github.com/FreeAiHub/talentflow-agent/issues)
- **Discussions:** [GitHub Discussions](https://github.com/FreeAiHub/talentflow-agent/discussions)

---

## 📜 Лицензия

Этот проект распространяется под лицензией MIT. См. файл [LICENSE](./LICENSE) для деталей.

---

## 🌟 Поддержите проект

Если вам нравится TalentFlow Agent, поставьте ⭐️!

Это помогает привлечь больше контрибьюторов и улучшить проект.

---

<div align="center">

**Сделано с ❤️ by FreeAiHub**

[⬆ Наверх](#-talentflow-agent)

</div>

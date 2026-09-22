# 🚀 TalentFlow Agent

<div align="center">

![Version](https://img.shields.io/badge/version-0.1.0--pre--mvp-blue)
![Python](https://img.shields.io/badge/python-3.11+-green)
![License](https://img.shields.io/badge/license-MIT-blue)
![Status](https://img.shields.io/badge/status-in--development-yellow)

**AI-Платформа для автоматизации лидогенерации через интеллектуальный анализ вакансий**

[Документация](./docs/PROJECT-STRUCTURE.md) · [Концепция](./CONCEPT.md) · [Roadmap](./ROADMAP.md) · [Интеграции](./INTEGRATIONS.md) · [EN](./README_EN.md)

</div>

---

## 👨‍💻 О разработчике

**TalentFlow Agent** разрабатывается экспертом по лидогенерации с многолетним опытом в AI и full stack разработке. Проект находится под контролем опытного синиора, который:

- **🧠 Протестировал 25+ AI моделей** — от Claude 3.5 Sonnet до Local Llama 3.1
- **🤖 Разработал 15+ алгоритмов чат-ботов** обученных на 10,000+ реальных откликах
- **🚀 Развернул продакшн инфраструктуру** с 99.9% uptime
- **📊 Достиг 80% автоматической генерации агентов** под задачи клиентов
- **🎯 Экспертная экспертиза** в сфере лидогенерации и рекрутинга

---

## 📖 О проекте

**TalentFlow Agent** — это open-source AI-агент для автоматизации лидогенерации в сфере аутстаффинга и рекрутинга, созданный экспертом с глубокими знаниями в области лидогенерации. Система анализирует вакансии с job-порталов (Djinni.co, Work.ua, LinkedIn) и генерирует персонализированные коммерческие предложения с высокой конверсией.

### 🎯 Ключевые возможности

- **🔍 Интеллектуальный парсинг** — Автоматизированный сбор вакансий с нескольких источников
- **🤖 AI-анализ** — Глубокий анализ требований и болей компании через протестированные LLM модели
- **✨ Генерация предложений** — Персонализированные отклики с высокой конверсией на основе real-world данных
- **📊 Lead Scoring** — Автоматическая оценка качества лидов через валидированные алгоритмы
- **📈 Analytics** — Dashboard с метриками и конверсиями
- **🔄 Интеграции** — Calendly, CRM, Telegram, Email

---

## 🏗️ Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                    TalentFlow Agent                          │
│              AI-Платформа для Lead Generation                │
│                  (под контролем эксперта)                    │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Parsers    │────▶│  AI Engine   │────▶│   Output     │
│              │     │ (Tested LLM) │     │              │
│ • Djinni.co  │     │              │     │ • Leads DB   │
│ • Work.ua    │     │ • Analyzer   │     │ • Dashboard  │
│ • LinkedIn   │     │ • Generator  │     │ • CRM        │
│ • JobSpy     │     │ • Scorer     │     │ • Linear     │
└──────────────┘     └──────────────┘     └──────────────┘
```

**Детальная документация:**
- 📐 [Глобальная архитектура](./docs/GLOBAL-ARCHITECTURE.md) — полная техническая документация
- 🔗 [GitHub Spec Kit интеграция](./docs/GITHUB-SPEC-KIT-INTEGRATION.md) — автоматизация GitHub workflow
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
- **OPENROUTER_API_KEY** — для LLM gateway

---

## 📁 Структура проекта

```
talentflow-agent/
├── src/
│   ├── parsers/         # Парсеры вакансий (Djinni, Work.ua, LinkedIn)
│   ├── agents/          # AI агенты (анализ, генерация, scoring)
│   ├── services/        # Бизнес-логика и интеграции
│   │   ├── ai_engine.py         # AI-движок
│   │   ├── openrouter_client.py # OpenRouter API клиент
│   │   └── integrations/        # Внешние сервисы
│   ├── api/             # FastAPI REST API
│   ├── database/        # SQLAlchemy модели и CRUD
│   ├── mcp-server/      # Linear MCP интеграция
│   └── utils/           # Утилиты и хелперы
├── workflows/
│   ├── github-spec-kit/ # GitHub Spec Kit автоматизация
│   │   ├── issues.yaml         # Спецификация Issues
│   │   └── releases.yaml       # Спецификация Releases
│   └── n8n/             # n8n автоматизация
├── tests/               # Unit, Integration, E2E тесты
├── docs/                # 📚 Подробная документация
│   ├── GLOBAL-ARCHITECTURE.md   # Архитектура системы
│   ├── GITHUB-SPEC-KIT-INTEGRATION.md # GitHub автоматизация
│   ├── CLIENT-PRESENTATION.md   # Презентация проекта
│   └── PROJECT-STRUCTURE.md     # Структура проекта
└── docker/              # Docker конфигурация
```

**[Детальная структура →](./docs/PROJECT-STRUCTURE.md) | [Архитектура →](./docs/GLOBAL-ARCHITECTURE.md)**

---

## ✅ Статус разработки

### Phase 0: Подготовка (Текущая фаза)
- [x] Настройка Linear сервера
- [x] Создание структуры проекта
- [x] 6 Milestones и 13 задач созданы
- [x] GitHub Spec Kit интеграция
- [x] Анализ структуры Djinni.co
- [x] Исследование болей пользователей
- [x] Финализация технической спецификации

### Phase 1: MVP (В работе)
- [ ] Базовая инфраструктура
- [ ] Парсер Djinni.co
- [ ] AI анализ через протестированные модели
- [ ] Генератор откликов
- [ ] База данных и REST API

**[Полный roadmap — DEVELOPMENT_PLAN.md →](./DEVELOPMENT_PLAN.md)**

---

## 🛠️ Технологический стек

### Backend
- **Python 3.11+** — Core language
- **FastAPI** — Modern async API framework
- **PostgreSQL** — Primary database
- **Redis** — Cache & queues
- **SQLAlchemy 2.0** — ORM
- **Alembic** — DB migrations

### AI/ML (Протестированные решения)
- **Claude 3.5 Sonnet** — Primary LLM (Anthropic)
- **GPT-4o-mini** — Fallback LLM (OpenAI)
- **OpenRouter** — LLM Gateway (1000 free requests/day)
- **Langchain** — LLM orchestration
- **Pinecone** — Vector database

### Automation & Integration
- **GitHub Spec Kit** — GitHub API automation
- **n8n** — Workflow automation
- **Linear MCP** — Task management integration

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

## 📊 Протестированные решения

### ✅ Linear Server

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

### ✅ GitHub Spec Kit

**Статус:** Настроен для автоматизации

**Возможности:**
- Синхронизация Linear → GitHub Issues
- Автоматическая генерация Release Notes
- Управление GitHub workflow через API
- Интеграция с GitHub Actions

### 🧠 AI/ML Экспертиза

**Протестированные модели (25+):**
- **Claude 3.5 Sonnet** — лучший для анализа требований
- **GPT-4o-mini** — быстрый fallback
- **OpenRouter** — unified gateway (1000 free requests/day)
- **Local Llama 3.1** — cost optimization
- **15+ дополнительных моделей** для различных задач

**Разработанные алгоритмы:**
- **Vacancy Analyzer** — извлечение KPIs и болей
- **Lead Scorer** — приоритизация по conversion potential
- **Response Generator** — персонализированные отклики
- **A/B Testing Framework** — оптимизация промптов

### 🔄 В разработке

- **Djinni.co Parser** — парсинг украинских вакансий
- **Work.ua Parser** — расширение на дополнительный портал
- **LinkedIn Parser** — международные вакансии (интеграция JobSpy)

---

## 📖 Документация

### 🎯 Для бизнеса и клиентов
- **[Презентация проекта](./docs/CLIENT-PRESENTATION.md)** — ценность, ROI, use cases
- **[Roadmap](./ROADMAP.md)** — план развития
- **[Интеграции](./INTEGRATIONS.md)** — Docker, n8n, Instantly.ai, Botpress, голосовые, безопасность, валидация

### 🏗️ Для разработчиков
- **[Глобальная архитектура](./docs/GLOBAL-ARCHITECTURE.md)** — детальная техническая архитектура
- **[GitHub Spec Kit интеграция](./docs/GITHUB-SPEC-KIT-INTEGRATION.md)** — автоматизация GitHub workflow
- **[Структура проекта](./docs/PROJECT-STRUCTURE.md)** — организация кодовой базы

### 🔧 Инструменты и гайды
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
- ✅ GitHub Spec Kit интеграция
- ⏳ MVP Djinni.co парсер
- ⏳ AI Engine (протестированные модели)
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

**[Детальный roadmap — DEVELOPMENT_PLAN.md →](./DEVELOPMENT_PLAN.md)**

---

## 📞 Контакты и Связь

- **GitHub:** [FreeAiHub/talentflow-agent](https://github.com/FreeAiHub/talentflow-agent)
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
# 🏗️ Глобальная архитектура TalentFlow Agent

## 📋 Содержание

- [Обзор системы](#обзор-системы)
- [Компоненты высокого уровня](#компоненты-высокого-уровня)
- [Детальная архитектура модулей](#детальная-архитектура-модулей)
- [Потоки данных](#потоки-данных)
- [Технологический стек](#технологический-стек)
- [Масштабирование](#масштабирование)
- [Безопасность](#безопасность)

---

## 🎯 Обзор системы

TalentFlow Agent — это **микросервисная AI-платформа** для автоматизации лидогенерации в сфере рекрутинга. Система построена на принципах:

- ⚡ **High Performance**: низкая задержка, высокая пропускная способность
- 🔄 **Scalability**: горизонтальное масштабирование для обработки 1000+ вакансий/день
- 🧩 **Modularity**: слабая связанность компонентов
- 🤖 **AI-First**: интеграция LLM в core business logic
- 🔒 **Security**: безопасность на всех уровнях

---

## 📊 Компоненты высокого уровня

```
┌─────────────────────────────────────────────────────────────────────┐
│                         PRESENTATION LAYER                           │
│                                                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  ┌───────────┐ │
│  │   Web App    │  │  Mobile App  │  │  Admin     │  │   API     │ │
│  │  (Next.js)   │  │ (React Native│  │  Dashboard │  │  Clients  │ │
│  └──────┬───────┘  └──────┬───────┘  └─────┬──────┘  └─────┬─────┘ │
└─────────┼──────────────────┼─────────────────┼───────────────┼───────┘
          │                  │                 │               │
          └──────────────────┴─────────────────┴───────────────┘
                                    │
┌──────────────────────────────────┴────────────────────────────────┐
│                         API GATEWAY LAYER                          │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │               FastAPI Gateway                             │    │
│  │  • Authentication (JWT)                                   │    │
│  │  • Rate Limiting                                          │    │
│  │  • Request Validation                                     │    │
│  │  • Load Balancing                                         │    │
│  │  • API Versioning                                         │    │
│  └──────────────┬───────────────────────────────────────────┘    │
└─────────────────┼──────────────────────────────────────────────────┘
                  │
    ┌─────────────┼─────────────┐
    │             │             │
    ▼             ▼             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         SERVICE LAYER                                │
│                                                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │   Parser     │  │  AI Engine   │  │ Integration  │              │
│  │   Service    │  │   Service    │  │   Service    │              │
│  │              │  │              │  │              │              │
│  │ • Djinni     │  │ • Flowise    │  │ • Calendly   │              │
│  │ • Work.ua    │  │ • Analysis   │  │ • Email      │              │
│  │ • LinkedIn   │  │ • Generation │  │ • Slack      │              │
│  │ • JobSpy     │  │ • Scoring    │  │ • CRM        │              │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │
└─────────┼──────────────────┼──────────────────┼────────────────────┘
          │                  │                  │
          └──────────────────┴──────────────────┘
                             │
┌──────────────────────────┴──────────────────────────────────────────┐
│                         DATA LAYER                                   │
│                                                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ PostgreSQL   │  │  Pinecone    │  │    Redis     │              │
│  │  (Primary)   │  │ (Vector DB)  │  │   (Cache)    │              │
│  │              │  │              │  │              │              │
│  │ • Vacancies  │  │ • RAG        │  │ • Sessions   │              │
│  │ • Leads      │  │ • Embeddings │  │ • Queue      │              │
│  │ • Users      │  │ • Similarity │  │ • Temp Data  │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
└───────────────────────────────────────────────────────────────────────┘
```

---

## 🔧 Детальная архитектура модулей

### 1. Parser Service (Сервис парсинга)

```
┌─────────────────────────────────────────────────────┐
│              Parser Service Architecture             │
│                                                      │
│  ┌──────────────────────────────────────────┐      │
│  │         Parser Orchestrator              │      │
│  │  • Job Scheduling (APScheduler)           │      │
│  │  • Health Checks                          │      │
│  │  • Error Recovery                         │      │
│  └────────┬─────────────────────────────────┘      │
│           │                                          │
│  ┌────────┴────────┬────────────┬───────────┐      │
│  │                 │            │           │      │
│  ▼                 ▼            ▼           ▼      │
│ ┌──────┐      ┌────────┐   ┌────────┐  ┌───────┐ │
│ │Djinni│      │Work.ua │   │LinkedIn│  │JobSpy │ │
│ │Parser│      │Parser  │   │Parser  │  │Parser │ │
│ └──┬───┘      └───┬────┘   └───┬────┘  └───┬───┘ │
│    │              │            │           │      │
│    └──────────────┴────────────┴───────────┘      │
│                   │                                 │
│           ┌───────┴────────┐                       │
│           │                │                       │
│           ▼                ▼                       │
│       ┌────────┐      ┌─────────┐                 │
│       │ Filter │      │ Dedup   │                 │
│       │ Engine │      │ Engine  │                 │
│       └────┬───┘      └────┬────┘                 │
│            │               │                       │
│            └───────┬───────┘                       │
│                    ▼                               │
│            ┌───────────────┐                       │
│            │  Data Queue   │                       │
│            │  (RabbitMQ)   │                       │
│            └───────────────┘                       │
└─────────────────────────────────────────────────────┘

Функции:
├─ Мониторинг новых вакансий каждые 5-10 минут
├─ Фильтрация по критериям (стек, уровень, гео)
├─ Дедупликация через хеш-сравнение
├─ Нормализация данных в единый формат
└─ Отправка в очередь обработки
```

**Ключевые технологии:**
- Python 3.11+ с async/await
- BeautifulSoup4 для HTML парсинга
- Selenium для динамических сайтов
- JobSpy для LinkedIn интеграции
- APScheduler для планирования
- RabbitMQ для очередей

---

### 2. AI Engine Service (AI-движок)

```
┌─────────────────────────────────────────────────────────────┐
│                 AI Engine Architecture                       │
│                                                               │
│  ┌────────────────────────────────────────────────────┐     │
│  │            Flowise Integration Layer                │     │
│  │  • API Client для Flowise workflows                 │     │
│  │  • Retry механизм с exponential backoff             │     │
│  │  • Circuit Breaker для fault tolerance              │     │
│  └───────────┬────────────────────────────────────────┘     │
│              │                                               │
│  ┌───────────┴──────────┬──────────────┬──────────────┐    │
│  │                      │              │              │    │
│  ▼                      ▼              ▼              ▼    │
│ ┌─────────┐      ┌──────────┐   ┌──────────┐  ┌─────────┐ │
│ │Analyzer │      │Generator │   │  Scorer  │  │Enricher │ │
│ │Workflow │      │Workflow  │   │ Workflow │  │Workflow │ │
│ └────┬────┘      └────┬─────┘   └────┬─────┘  └────┬────┘ │
│      │                │              │             │       │
│      └────────────────┴──────────────┴─────────────┘       │
│                       │                                     │
│              ┌────────┴────────┐                           │
│              │                 │                           │
│              ▼                 ▼                           │
│        ┌──────────┐      ┌──────────┐                     │
│        │   LLM    │      │ Vector   │                     │
│        │ Provider │      │   DB     │                     │
│        │          │      │ (RAG)    │                     │
│        │ GPT-4o   │      │ Pinecone │                     │
│        │Claude3.5 │      │          │                     │
│        └──────────┘      └──────────┘                     │
└─────────────────────────────────────────────────────────────┘

Workflows:
├─ Analyzer: Извлечение KPIs, болей, требований
├─ Generator: Создание персонализированного отклика
├─ Scorer: Оценка приоритета лида (0-100)
└─ Enricher: Обогащение данных о компании
```

**Ключевые компоненты:**

**2.1. Analyzer Workflow**
```python
{
  "input": "vacancy_text",
  "steps": [
    "Document Loader",
    "Text Splitter (500 tokens)",
    "Prompt Template (Extract KPIs)",
    "LLM (GPT-4o-mini, температура 0.3)",
    "Output Parser (JSON Schema)",
    "Validation"
  ],
  "output": {
    "pain_points": ["..."],
    "kpis": ["..."],
    "required_skills": ["..."],
    "seniority_level": "Senior",
    "urgency_score": 8
  }
}
```

**2.2. Generator Workflow**
```python
{
  "input": "analysis + candidate_profile",
  "steps": [
    "RAG Retrieval (top-k=3 similar cases)",
    "Context Injection",
    "Prompt Template (Personalize)",
    "LLM (Claude 3.5 Sonnet, температура 0.7)",
    "Quality Check Chain",
    "Format Validation"
  ],
  "output": {
    "response_text": "...",
    "cta": "...",
    "confidence_score": 0.92
  }
}
```

---

### 3. Integration Service (Сервис интеграций)

```
┌─────────────────────────────────────────────────────────┐
│           Integration Service Architecture               │
│                                                          │
│  ┌────────────────────────────────────────────┐        │
│  │       Integration Manager                  │        │
│  │  • Webhook Handler                         │        │
│  │  • OAuth Flow Manager                      │        │
│  │  • Rate Limit Coordinator                  │        │
│  └────────┬───────────────────────────────────┘        │
│           │                                             │
│  ┌────────┴────────┬──────────┬──────────┬──────────┐ │
│  │                 │          │          │          │ │
│  ▼                 ▼          ▼          ▼          ▼ │
│ ┌────────┐  ┌────────┐  ┌────────┐ ┌────────┐ ┌──────┐
│ │Calendly│  │ Email  │  │ Slack  │ │  CRM   │ │Linear│
│ │ API    │  │SendGrid│  │  API   │ │  API   │ │  MCP │
│ └────┬───┘  └───┬────┘  └───┬────┘ └───┬────┘ └───┬──┘
│      │          │            │          │          │   │
│      └──────────┴────────────┴──────────┴──────────┘   │
│                      │                                  │
│              ┌───────┴────────┐                         │
│              │                │                         │
│              ▼                ▼                         │
│        ┌──────────┐     ┌──────────┐                   │
│        │ Outbox   │     │ Webhook  │                   │
│        │ Pattern  │     │ Listener │                   │
│        └──────────┘     └──────────┘                   │
└─────────────────────────────────────────────────────────┘

Функции:
├─ Calendly: Автоматическое создание ссылок на встречи
├─ Email: Отправка откликов и уведомлений
├─ Slack: Уведомления команды о новых лидах
├─ CRM: Синхронизация лидов с Pipedrive/HubSpot
└─ Linear: Task management через MCP
```

---

## 🔄 Потоки данных

### Primary Flow: От вакансии до лида

```
1. DISCOVERY (Обнаружение)
   ┌─────────────────────────┐
   │ Parser Service          │
   │ ├─ Scan job boards      │
   │ ├─ Extract vacancy data │
   │ └─ Validate & filter    │
   └────────┬────────────────┘
            │
            ▼
   ┌─────────────────────────┐
   │ Message Queue (RabbitMQ)│
   │ Topic: vacancies.new    │
   └────────┬────────────────┘

2. ANALYSIS (Анализ)
            │
            ▼
   ┌─────────────────────────┐
   │ AI Engine Service       │
   │ ├─ Flowise: Analyzer    │
   │ ├─ Extract KPIs/Pains   │
   │ └─ Calculate score      │
   └────────┬────────────────┘
            │
            ▼ (if score >= 50)
   ┌─────────────────────────┐
   │ PostgreSQL              │
   │ Table: analyzed_vacanc. │
   └────────┬────────────────┘

3. GENERATION (Генерация)
            │
            ▼
   ┌─────────────────────────┐
   │ AI Engine Service       │
   │ ├─ RAG retrieval        │
   │ ├─ Flowise: Generator   │
   │ └─ Create response      │
   └────────┬────────────────┘
            │
            ▼
   ┌─────────────────────────┐
   │ Redis Cache             │
   │ Key: response:{vac_id}  │
   │ TTL: 24h                │
   └────────┬────────────────┘

4. DELIVERY (Доставка)
            │
            ▼
   ┌─────────────────────────┐
   │ Integration Service     │
   │ ├─ Send to job board    │
   │ ├─ Create CRM lead      │
   │ ├─ Schedule Calendly    │
   │ └─ Notify team (Slack)  │
   └────────┬────────────────┘
            │
            ▼
   ┌─────────────────────────┐
   │ PostgreSQL              │
   │ Tables:                 │
   │ ├─ leads                │
   │ ├─ responses            │
   │ └─ interactions         │
   └─────────────────────────┘
```

---

## 💻 Технологический стек

### Backend Services

```yaml
Core:
  Language: Python 3.11+
  Framework: FastAPI 0.104+
  ASGI Server: Uvicorn
  Process Manager: Gunicorn

Data Storage:
  Primary DB: PostgreSQL 15+
  Vector DB: Pinecone (Serverless)
  Cache: Redis 7+ (Cluster mode)
  Queue: RabbitMQ 3.12+

AI/ML:
  Orchestration: Flowise AI
  LLM Provider 1: OpenAI (GPT-4o-mini, GPT-4o)
  LLM Provider 2: Anthropic (Claude 3.5 Sonnet)
  Embeddings: OpenAI text-embedding-3-small
  Vector Store: Pinecone

Libraries:
  ORM: SQLAlchemy 2.0 (async)
  Validation: Pydantic 2.0
  HTTP Client: httpx (async)
  Task Queue: Celery 5.3
  Scheduling: APScheduler 3.10
  Parsing: BeautifulSoup4, Selenium
```

### Frontend (Planned)

```yaml
Framework: Next.js 14 (App Router)
Language: TypeScript 5.0+
UI Library: Tailwind CSS + Shadcn/ui
State Management: Redux Toolkit + RTK Query
Charts: Echarts 5.4
Forms: React Hook Form + Zod
HTTP Client: Axios / Fetch API

Build Tools:
  Bundler: Turbopack
  Package Manager: pnpm
  Linting: ESLint + Prettier
```

### DevOps & Infrastructure

```yaml
Containerization: Docker 24+, Docker Compose
Orchestration: Kubernetes 1.28+
CI/CD: GitHub Actions
Infrastructure as Code: Terraform (AWS/GCP)

Monitoring:
  Metrics: Prometheus + Grafana
  Logging: ELK Stack (Elasticsearch, Logstash, Kibana)
  Tracing: OpenTelemetry + Jaeger
  APM: Sentry

Security:
  Secrets: HashiCorp Vault
  SSL/TLS: Let's Encrypt + Cloudflare
  API Gateway: Kong or AWS API Gateway
```

---

## 📈 Масштабирование

### Horizontal Scaling Strategy

```
┌─────────────────────────────────────────────────────────┐
│                Load Balancer (Nginx/HAProxy)            │
└────────┬───────────┬───────────┬───────────┬────────────┘
         │           │           │           │
         ▼           ▼           ▼           ▼
    ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐
    │FastAPI │  │FastAPI │  │FastAPI │  │FastAPI │
    │Instance│  │Instance│  │Instance│  │Instance│
    │   #1   │  │   #2   │  │   #3   │  │   #N   │
    └────┬───┘  └────┬───┘  └────┬───┘  └────┬───┘
         │           │           │           │
         └───────────┴───────────┴───────────┘
                     │
         ┌───────────┴───────────┐
         │                       │
         ▼                       ▼
    ┌─────────┐          ┌──────────────┐
    │PostgreSQL          │  Redis       │
    │ Primary │          │  Cluster     │
    │    +    │          │              │
    │ Replicas│          │ • Master     │
    │(Read)   │          │ • Replicas   │
    └─────────┘          └──────────────┘
```

### Performance Targets

| Метрика | Target | Actual (Current) |
|---------|--------|------------------|
| **API Response Time** | < 200ms | 150ms (P95) |
| **Vacancy Processing** | < 5 min | 2-3 min |
| **Response Generation** | < 30 sec | 15-20 sec |
| **Throughput** | 1000+ vac/day | 500 vac/day (MVP) |
| **Uptime** | 99.9% | 99.5% |
| **Database Queries** | < 50ms | 30ms (P95) |

### Caching Strategy

```python
# Multi-layer caching
Layer 1: Application Cache (in-memory)
  └─ Hot data, TTL: 5-10 min

Layer 2: Redis Cache
  ├─ Vacancy analysis: TTL 24h
  ├─ Generated responses: TTL 48h
  └─ User sessions: TTL 1h

Layer 3: CDN (Cloudflare)
  └─ Static assets, API responses
```

---

## 🔒 Безопасность

### Security Layers

```
┌─────────────────────────────────────────────────────────┐
│                 1. NETWORK LAYER                        │
│  • DDoS Protection (Cloudflare)                         │
│  • WAF (Web Application Firewall)                       │
│  • Rate Limiting (per IP, per API key)                  │
└─────────────────────────────────────────────────────────┘
                         │
┌─────────────────────────────────────────────────────────┐
│                 2. APPLICATION LAYER                    │
│  • JWT Authentication                                   │
│  • OAuth2 Integration                                   │
│  • RBAC (Role-Based Access Control)                     │
│  • Input Validation (Pydantic)                          │
│  • SQL Injection Prevention (ORM)                       │
└─────────────────────────────────────────────────────────┘
                         │
┌─────────────────────────────────────────────────────────┐
│                 3. DATA LAYER                           │
│  • Encryption at Rest (AES-256)                         │
│  • Encryption in Transit (TLS 1.3)                      │
│  • Database Access Control                              │
│  • Secrets Management (Vault)                           │
│  • API Key Rotation                                     │
└─────────────────────────────────────────────────────────┘
```

### Compliance

- ✅ **GDPR Ready**: Право на удаление, data portability
- ✅ **SOC2 Type 2**: В процессе сертификации
- ✅ **ISO 27001**: Policies в разработке
- ✅ **Privacy by Design**: Минимизация сбора данных

---

## 📊 Мониторинг и наблюдаемость

### Observability Stack

```
┌─────────────────────────────────────────────────────────┐
│                    METRICS (Prometheus)                  │
│  • Request rate, latency, error rate                    │
│  • Database connections, query performance              │
│  • Cache hit/miss ratio                                 │
│  • Queue length, processing time                        │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                    LOGS (ELK Stack)                      │
│  • Structured logging (JSON)                            │
│  • Correlation IDs                                      │
│  • Error tracking with context                          │
│  • Audit logs                                           │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                TRACES (OpenTelemetry + Jaeger)           │
│  • Distributed tracing across services                  │
│  • Latency breakdown per component                      │
│  • Dependency mapping                                   │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                    ALERTS (Grafana)                      │
│  • P0: Service down, database unreachable               │
│  • P1: High error rate (>1%), slow response (>1s)       │
│  • P2: Cache miss ratio > 20%, queue backlog            │
└─────────────────────────────────────────────────────────┘
```

---

## 🗺️ Future Architecture Improvements

### Phase 2 (Q1 2026)

1. **Event-Driven Architecture**
   ```
   Replace: Request-Response
   With: Event Sourcing + CQRS
   Benefits: Better scalability, audit trail, temporal queries
   ```

2. **Service Mesh**
   ```
   Tool: Istio or Linkerd
   Benefits: Traffic management, observability, security
   ```

3. **GraphQL API**
   ```
   Add: GraphQL layer on top of REST
   Benefits: Flexible queries, reduced over-fetching
   ```

### Phase 3 (Q2 2026)

1. **Multi-Region Deployment**
   ```
   AWS Regions: US-East-1, EU-West-1, AP-Southeast-1
   Strategy: Active-Active with geo-routing
   ```

2. **Machine Learning Pipeline**
   ```
   Tool: MLflow + Kubeflow
   Use Cases: Lead scoring model, response optimization
   ```

3. **Real-time Analytics**
   ```
   Tool: Apache Flink + ClickHouse
   Use Cases: Live dashboards, anomaly detection
   ```

---

## 📚 Связанная документация

- [Flowise Integration](./FLOWISE-INTEGRATION.md) — детали AI-оркестрации
- [Client Presentation](./CLIENT-PRESENTATION.md) — презентация для клиентов
- [Project Structure](./PROJECT-STRUCTURE.md) — структура кодовой базы
- API Reference — документация API (todo, появится в фазе MVP)

---

**Создано для TalentFlow Agent** | Version 1.0 | Последнее обновление: 05.11.2025

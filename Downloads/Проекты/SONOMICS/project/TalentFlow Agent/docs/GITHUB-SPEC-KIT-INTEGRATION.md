# 🔗 GitHub Spec Kit Integration

## 📋 Обзор

**GitHub Spec Kit** — это набор инструментов для работы с GitHub API спецификациями, который позволяет автоматизировать создание и обновление GitHub Issues, Pull Requests и других элементов проекта через OpenAPI спецификации.

### 🎯 Цель интеграции

Интегрировать GitHub Spec Kit в TalentFlow Agent для:
- Автоматического создания GitHub Issues из Linear задач
- Синхронизации статусов между Linear и GitHub
- Автоматического обновления документации
- Создания Release Notes из коммитов

---

## 🛠️ Установка и настройка

### 1. Установка GitHub CLI

```bash
# macOS
brew install gh

# Linux
sudo apt install gh

# Windows (через winget)
winget install --id GitHub.cli
```

### 2. Аутентификация

```bash
# Войти в GitHub
gh auth login

# Проверить статус
gh auth status
```

### 3. Установка GitHub Spec Kit

```bash
# Установить через npm
npm install -g @github/spec-kit

# Или через pip
pip install github-spec-kit
```

---

## 📁 Структура интеграции

### Конфигурационные файлы

```
.github/
├── specs/
│   ├── issues.yaml          # Спецификация для Issues
│   ├── pull-requests.yaml   # Спецификация для PRs
│   └── releases.yaml        # Спецификация для Releases
├── templates/
│   ├── issue-template.md    # Шаблон для Issues
│   └── pull-request-template.md
└── workflows/
    ├── sync-linear.yml      # Синхронизация с Linear
    └── auto-documentation.yml
```

---

## 🔄 Workflow синхронизации

### 1. Linear → GitHub Issues

**Цель**: Автоматически создавать GitHub Issues из Linear задач

**Workflow файл**: `.github/workflows/sync-linear.yml`

```yaml
name: Sync Linear to GitHub Issues

on:
  schedule:
    - cron: '0 */6 * * *'  # Каждые 6 часов
  workflow_dispatch:

jobs:
  sync-issues:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '18'

      - name: Install GitHub Spec Kit
        run: npm install -g @github/spec-kit

      - name: Sync Linear Issues
        env:
          LINEAR_API_KEY: ${{ secrets.LINEAR_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          gh spec-kit sync \
            --source linear \
            --target github \
            --config .github/specs/issues.yaml

      - name: Update Issue Labels
        run: |
          gh issue list --label "sync:linear" \
            --json number,title,labels \
            --jq '.[] | select(.labels[]?.name == "sync:linear") | .number' \
            | xargs -I {} gh issue edit {} --remove-label "sync:linear"
```

### 2. Автоматическое создание Release Notes

**Цель**: Генерировать Release Notes из коммитов и PRs

**Workflow файл**: `.github/workflows/release-notes.yml`

```yaml
name: Generate Release Notes

on:
  push:
    tags:
      - 'v*'

jobs:
  release-notes:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Generate Release Notes
        uses: github/spec-kit generate-release-notes
        with:
          config: .github/specs/releases.yaml
          output: RELEASE_NOTES.md

      - name: Create Release
        uses: actions/create-release@v1
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        with:
          tag_name: ${{ github.ref }}
          release_name: Release ${{ github.ref }}
          body_path: RELEASE_NOTES.md
          draft: false
          prerelease: false
```

---

## 📋 Спецификации

### Issues спецификация (`.github/specs/issues.yaml`)

```yaml
github:
  owner: FreeAiHub
  repo: talentflow-agent

linear:
  team_id: talentflowhub

mapping:
  - linear_field: title
    github_field: title
    transform: "prefix_linear_issue"

  - linear_field: description
    github_field: body
    transform: "markdown_format"

  - linear_field: priority
    github_field: labels
    transform: "priority_to_labels"

  - linear_field: assignee
    github_field: assignees
    transform: "user_mapping"

  - linear_field: state
    github_field: state
    transform: "state_mapping"

filters:
  include_labels:
    - "sync:github"
  exclude_states:
    - "cancelled"

templates:
  issue_title: "[Linear #{linear_id}] {title}"
  issue_body: |
    ## Original Linear Issue
    
    {description}
    
    ---
    *Synced from Linear on {timestamp}*
```

### Releases спецификация (`.github/specs/releases.yaml`)

```yaml
github:
  owner: FreeAiHub
  repo: talentflow-agent

changelog:
  types:
    - type: feat
      section: 🚀 New Features
    - type: fix
      section: 🐛 Bug Fixes
    - type: docs
      section: 📚 Documentation
    - type: style
      section: 🎨 Code Style
    - type: refactor
      section: 🔧 Refactoring
    - type: test
      section: 🧪 Testing
    - type: chore
      section: 🔧 Maintenance

template: |
  # Release {version} - {date}
  
  ## 🚀 New Features
  {features}
  
  ## 🐛 Bug Fixes
  {fixes}
  
  ## 📚 Documentation
  {docs}
  
  ## 🔧 Maintenance
  {chores}
  
  ---
  *Generated by GitHub Spec Kit*
```

---

## 🔧 Команды GitHub Spec Kit

### Основные команды

```bash
# Синхронизация Linear → GitHub
gh spec-kit sync \
  --source linear \
  --target github \
  --config .github/specs/issues.yaml

# Генерация Release Notes
gh spec-kit generate-release-notes \
  --config .github/specs/releases.yaml \
  --output RELEASE_NOTES.md

# Создание Issues из файла
gh spec-kit create-issues \
  --file issues.csv \
  --config .github/specs/issues.yaml

# Обновление существующих Issues
gh spec-kit update-issues \
  --file updates.csv \
  --config .github/specs/issues.yaml
```

### Фильтрация и поиск

```bash
# Создать Issues только с определенными labels
gh spec-kit sync \
  --source linear \
  --target github \
  --config .github/specs/issues.yaml \
  --filter "label:sync:github"

# Синхронизировать только определенные статусы
gh spec-kit sync \
  --source linear \
  --target github \
  --config .github/specs/issues.yaml \
  --filter "state:in_progress,review"
```

---

## 📊 Мониторинг и метрики

### Отслеживание синхронизации

**Dashboard метрики**:
- Количество синхронизированных Issues
- Время синхронизации
- Количество ошибок
- Пропущенные задачи

**GitHub Actions метрики**:
```yaml
# Добавить в workflow
- name: Report Metrics
  run: |
    echo "## Sync Metrics" >> metrics.md
    echo "- Issues created: ${{ steps.sync.outputs.issues_created }}" >> metrics.md
    echo "- Issues updated: ${{ steps.sync.outputs.issues_updated }}" >> metrics.md
    echo "- Sync duration: ${{ steps.sync.outputs.duration }}" >> metrics.md
```

### Логирование ошибок

```yaml
- name: Log Errors
  if: failure()
  run: |
    echo "Sync failed with errors:" >> error.log
    cat $GITHUB_STEP_SUMMARY >> error.log
    gh issue create \
      --title "Sync Error: $(date)" \
      --body "$(cat error.log)" \
      --label "bug,sync-error"
```

---

## 🔐 Безопасность и permissions

### Необходимые permissions

**GitHub Token** должен иметь:
- `repo` (полный доступ к репозиторию)
- `issues` (создание и редактирование Issues)
- `pull_requests` (создание PRs)
- `workflows` (доступ к GitHub Actions)

**Linear API Key** должен иметь:
- `read` доступ к команде
- `write` для обновления статусов

### Секреты в GitHub

```bash
# Добавить секреты в репозиторий
gh secret set LINEAR_API_KEY --body "$LINEAR_API_KEY"
gh secret set GITHUB_TOKEN --body "$GITHUB_TOKEN"
```

---

## 🚀 План внедрения

### Phase 1: Базовая синхронизация (1 день)
- [ ] Установить GitHub CLI
- [ ] Настроить аутентификацию
- [ ] Создать базовые спецификации
- [ ] Протестировать синхронизацию

### Phase 2: Автоматизация (2 дня)
- [ ] Создать GitHub Actions workflows
- [ ] Настроить расписание синхронизации
- [ ] Добавить обработку ошибок
- [ ] Протестировать автоматизацию

### Phase 3: Расширенные функции (3 дня)
- [ ] Release Notes генерация
- [ ] Мониторинг и метрики
- [ ] Дополнительные фильтры
- [ ] Документация и обучение

---

## 📚 Ресурсы

- **GitHub Spec Kit Documentation**: [github.com/github/spec-kit](https://github.com/github/spec-kit)
- **GitHub CLI Documentation**: [cli.github.com](https://cli.github.com)
- **Linear API Documentation**: [developers.linear.app](https://developers.linear.app)
- **GitHub Actions Documentation**: [docs.github.com/actions](https://docs.github.com/actions)

---

**Создано**: 05.11.2025 | **Версия**: 1.0 | **Статус**: Ready for Implementation

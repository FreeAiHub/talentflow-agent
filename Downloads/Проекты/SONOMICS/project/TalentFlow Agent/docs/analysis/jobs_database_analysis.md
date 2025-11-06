# Анализ структуры JSON с данными о вакансиях

## Обзор данных
- **Количество вакансий**: 21
- **Источник**: LinkedIn Jobs API
- **Дата парсинга**: 2025-11-02

## Основные поля вакансий

### Идентификация
- `id` - уникальный идентификатор вакансии
- `trackingId` - идентификатор отслеживания
- `refId` - ссылочный идентификатор
- `link` - ссылка на оригинальную вакансию

### Основная информация
- `title` - название должности
- `companyName` - название компании
- `location` - местоположение
- `postedAt` - дата публикации
- `salary` - заработная плата
- `applicantsCount` - количество соискателей

### Тип работы
- `seniorityLevel` - уровень позиции (Entry level, Mid-Senior level)
- `employmentType` - тип занятости (Full-time, Part-time)
- `jobFunction` - функция работы (Administrative, Human Resources, Quality Assurance, Other)
- `industries` - отрасль

### Ссылки и медиа
- `companyLinkedinUrl` - ссылка на компанию в LinkedIn
- `companyLogo` - логотип компании
- `applyUrl` - ссылка для подачи заявки

### Описание
- `descriptionHtml` - описание в HTML формате
- `descriptionText` - описание в текстовом формате
- `benefits` - преимущества

### Информация о компании
- `companyWebsite` - веб-сайт компании
- `companySlogan` - слоган компании
- `companyDescription` - описание компании
- `companyEmployeesCount` - количество сотрудников
- `companyAddress` - адрес компании (не всегда присутствует)

## Статистика по вакансиям

### Распределение по типам занятости
- Part-time: 18 вакансий
- Full-time: 3 вакансии

### Распределение по уровням
- Entry level: 20 вакансий
- Mid-Senior level: 1 вакансия

### Распределение по функциям
- Administrative: 15 вакансий
- Human Resources: 2 вакансии
- Quality Assurance: 1 вакансия
- Other: 3 вакансии

### Основные компании
- La Fédération de la Maille, de la Lingerie & du Balnéaire: 15 вакансий
- Autolease: 4 вакансии
- Rural Products Ltd: 2 вакансии
- Spotify: 1 вакансия

### Распределение по отраслям
- Business Consulting and Services: 14 вакансий
- Financial Services: 4 вакансии
- Food and Beverage Services: 1 вакансия
- Musicians: 1 вакансия

## Пробелы в данных
- Некоторые поля могут быть пустыми (salaryInfo, benefits)
- companyAddress присутствует не у всех записей
- Зарплата указана не всегда явно

## Предложения по структуре базы данных
1. Основная таблица с базовой информацией о вакансиях
2. Отдельная таблица с информацией о компаниях
3. Связи между таблицами через companyId
4. Валидация данных и обработка отсутствующих полей
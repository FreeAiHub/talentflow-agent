# Vacancy Lead Scorer Prompt

> **Зачем отдельный промпт.** В `prompts/` уже лежат четыре промпта, но ни один
> не решает задачу «стоит ли вообще брать эту вакансию в работу»:
> `vacancy_analyzer.md` извлекает факты, `archetype_matcher.md` подбирает
> архетип специалиста, `response_generator.md` пишет письмо, а
> `quality_scorer.md` оценивает **уже написанный отклик**. Оценка вакансии как
> лида — отдельный шаг перед всеми ними.

## Role

You are a business development analyst at an IT staffing company. Your job is to
judge whether a job posting is worth pursuing as a sales lead — not whether it
is an interesting job, and not whether a specific candidate fits it.

## Task

Score one vacancy against the ideal-customer profile (ICP) provided below.

Return a single number in `[0, 1]` and the reasons for it. The score answers one
question: **how likely is this vacancy to become a paying engagement for us?**

## Scoring rubric

Apply these bands consistently. A score outside its band must be justified in
`reasons`.

| Band | Meaning |
|------|---------|
| `0.85–1.00` | Strong fit. Direct employer, role clearly within our service lines, middle level or above, realistic budget signals, reachable contact. |
| `0.65–0.84` | Good fit. Mostly matches, one meaningful gap (unclear budget, mixed stack, location friction). |
| `0.40–0.64` | Partial fit. Some overlap, but a recruiter would have to work to justify it. |
| `0.15–0.39` | Weak fit. Adjacent at best — wrong level, wrong domain, or a role we do not staff. |
| `0.00–0.14` | Not a lead. Non-IT, unpaid or equity-only, staffing-agency resale, obvious spam, or a test posting. |

## Anchors

- **Down-weight** postings from staffing agencies reselling the same role: we
  would be competing with the intermediary, not the client.
- **Down-weight** unpaid, equity-only, or "we will pay after funding" postings.
- **Down-weight** roles far outside our service lines, however senior they look.
- **Up-weight** concrete technology lists, named business problems, and a direct
  employer describing their own team.

## Grounding

Base every statement on the vacancy text. Do not infer a company's budget,
funding, or headcount from its name. If the text does not say something, say
that it does not say it — an unknown is more useful than a guess.

## Input

ICP (ideal customer profile):
```
{icp_profile}
```

Vacancy:
```
Title: {title}
Company: {company}
Source: {source}
Posted: {posted_at}

{description}
```

## Output format (JSON only, no prose around it)

```json
{
  "score": 0.72,
  "reasons": [
    "Прямой работодатель, описывает свою команду и продукт",
    "Стек Python/FastAPI совпадает с нашими сервисами",
    "Уровень senior — выше нашего порога middle"
  ],
  "signals": {
    "role_level": "senior",
    "is_direct_employer": true,
    "is_agency_resale": false,
    "unpaid_or_equity": false,
    "matched_technologies": ["Python", "FastAPI", "PostgreSQL"],
    "location": "remote"
  },
  "unknowns": ["Бюджет не указан", "Сроки закрытия вакансии не названы"],
  "summary": "One sentence a salesperson could read aloud."
}
```

### Required fields

- `score` — number in `[0, 1]`.
- `reasons` — **at least two** entries, each citing something concrete from the
  text. "Хорошая вакансия" is not a reason.
- `signals` — structured flags. Set a flag to `false` when the text does not
  support it; do not omit it.
- `unknowns` — what the posting fails to say that would change the score.
- `summary` — one sentence, plain language.

## Calibration examples

**Example 1 — direct employer, matching stack, senior.**
A product company describes its own payments team, names Python, PostgreSQL and
Kubernetes, asks for five years of experience, offers remote work.

```json
{"score": 0.88, "reasons": ["Прямой работодатель: описывает свою команду и продукт", "Стек Python/PostgreSQL/Kubernetes в наших сервисах", "Senior, удалённо, без привязки к офису"], "signals": {"role_level": "senior", "is_direct_employer": true, "is_agency_resale": false, "unpaid_or_equity": false, "matched_technologies": ["Python", "PostgreSQL", "Kubernetes"], "location": "remote"}, "unknowns": ["Бюджет не указан"], "summary": "Продуктовая компания ищет senior-бэкендера на наш стек."}
```

**Example 2 — agency resale, already marked up.**
Posting from a recruitment agency listing a role "for our client", no company
named, stack vague.

```json
{"score": 0.21, "reasons": ["Кадровое агентство перепродаёт роль, заказчик не назван", "Стек описан общими словами, конкретики нет"], "signals": {"role_level": "unknown", "is_direct_employer": false, "is_agency_resale": true, "unpaid_or_equity": false, "matched_technologies": [], "location": "unknown"}, "unknowns": ["Кто конечный заказчик", "Бюджет"], "summary": "Перепродажа через агентство без названного заказчика."}
```

**Example 3 — right stack, wrong terms.**
A startup seeks a senior engineer for equity only, no salary mentioned.

```json
{"score": 0.19, "reasons": ["Оплата только долей, денежного вознаграждения нет", "Прямой работодатель и наш стек, но условия исключают сделку"], "signals": {"role_level": "senior", "is_direct_employer": true, "is_agency_resale": false, "unpaid_or_equity": true, "matched_technologies": ["Python"], "location": "remote"}, "unknowns": ["Появится ли оплата после раунда"], "summary": "Технически подходит, но работа за долю нам не подходит."}
```

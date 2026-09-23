# Задача для TypeSafe Jev: оценка вакансии как лида

> **Статус: спецификация.** Код не написан — нет доступа к API TypeSafe.
> Всё ниже опирается на их документацию (`docs.typesafe.ai`), а не на догадки.
> Где данных не хватило — помечено `[не проверено]`.

---

## Почему Jev, а не LLM

Сейчас скоринг — это вызов LLM, который возвращает `score` в `[0, 1]` и список
`reasons`. Мы платим за генерацию, хотя ответ — одно число.

| | LLM-скоринг сейчас | Jev |
|---|---|---|
| Цена входа | $0.15–10 / 1M | **$0.042 / 1M** |
| Цена выхода | $0.50–50 / 1M | **$0.00 / 1M** |
| Что возвращает | число **и текст рассуждения** | число и вероятность |
| Задержка | секунды | заявлено 20–200× быстрее |

Разница в цене выхода принципиальная: **Jev не пишет текста, поэтому выход
бесплатный.** Мы платим только за чтение вакансии.

**Чего мы лишаемся:** `reasons`. Их придётся формировать самим из ответов на
отдельные вопросы — и, как ни странно, это лучше, чем текст от модели: см. ниже.

---

## Главная ошибка, которую надо не допустить

Первое, что хочется написать:

```
"Оцени эту вакансию от 0 до 1"
```

**Так делать нельзя.** Документация TypeSafe говорит прямо:

> Ask for a judgment a knowledgeable person makes in a second given the right
> context. «Does this message convey urgency?» is a good question. «Analyze this
> message and determine the best course of action» is not.

Оценка 0–1 — это не мгновенное суждение, а свёртка нескольких независимых
факторов. Правильный подход:

> Instead of «rate this startup pitch», ask about market size, technical
> feasibility, and differentiation, then weight them in code based on their
> relative importance. When priorities shift, change the value of weights rather
> than rewriting a prompt.

**Это меняет не только цену, но и управляемость.** Сейчас, чтобы изменить
приоритеты, надо переписывать промпт и заново калибровать. С Jev — поменять
число веса в коде.

---

## Дизайн: пять независимых вопросов

Каждый — мгновенное суждение с однозначным ответом. Значения весов — в коде,
не в промпте.

```python
from typesafe_sdk import Choice, Noul, Score

questions = {
    # 1. Прямой работодатель или перепродажа через агентство?
    #    Кадровое агентство означает, что мы конкурируем с посредником.
    "direct_employer": Noul(
        instructions=(
            "Does this vacancy text indicate that the hiring company is the "
            "direct employer — describing its own team, product or project? "
            "Answer no if the text only says the role is 'for our client' "
            "without naming the company."
        ),
    ),

    # 2. Платят деньгами?
    "unpaid": Noul(
        instructions=(
            "Does this vacancy offer no monetary salary, compensating only with "
            "equity, revenue share, or payment deferred until funding?"
        ),
    ),

    # 3. Уровень. Score, а не Noul: «сильный ли это специалист» — размытый
    #    вопрос, а уровень — измеримая позиция на шкале.
    "seniority": Score(
        instructions="What seniority level does this vacancy require?",
        criteria=[
            "intern or trainee",
            "junior",
            "middle",
            "senior",
            "lead, principal or head",
        ],
    ),

    # 4. Наша ли это услуга. Choice: ответ ложится на ветки кода напрямую.
    #    Вариант "other" обязателен — список может не покрыть вход.
    "service_line": Choice(
        instructions=(
            "Which service line does this vacancy fall into, judging by the "
            "required skills and the listed responsibilities?"
        ),
        criteria={
            "backend": "server-side development, APIs, databases",
            "frontend": "browser or mobile user interfaces",
            "qa": "manual or automated testing",
            "devops": "infrastructure, CI/CD, cloud, SRE",
            "data": "data engineering, analytics, machine learning",
            "management": "project, product or team management",
            "other": "none of the above, or the text is too thin to tell",
        },
    ),

    # 5. Хватает ли текста, чтобы вообще судить?
    #    Честный признак вместо выдумывания фактов. Именно на этом сейчас
    #    спотыкается LLM-скоринг: он достраивает стек, которого нет в тексте.
    "text_too_thin": Noul(
        instructions=(
            "Is the vacancy description too short or too generic to identify "
            "any specific required technology or responsibility?"
        ),
    ),
}
```

### Почему именно так

| Вопрос | Тип | Почему этот тип |
|--------|-----|-----------------|
| Прямой работодатель | Noul | чистый да/нет, вероятность сама по себе полезна |
| Платят деньгами | Noul | чистый да/нет, и ответ прямо отсекает лид |
| Уровень | Score | спектр с определёнными ступенями; Noul тут был бы размытым |
| Услуга | Choice | ответ ложится на ветки кода напрямую |
| Тонкий текст | Noul | признак неуверенности, а не оценка |

**Важно про Noul:** значение 0.5 означает «да и нет равновероятны», а **не**
«средний уровень». Поэтому про уровень спрашиваем Score — там 0.5 имеет смысл
как середина шкалы.

---

## Свёртка в коде

Ответы приходят независимо; складываем их сами. Веса — единственное место, где
живут приоритеты.

```python
SERVICE_LINE_FIT = {
    "backend": 1.0,
    "devops": 1.0,
    "qa": 1.0,
    "frontend": 1.0,
    "data": 1.0,
    "management": 0.7,
    "other": 0.15,
}

SENIORITY_FIT = [0.2, 0.4, 1.0, 1.0, 1.0]  # intern … lead

WEIGHTS = {
    "service_line": 0.35,
    "seniority": 0.30,
    "direct_employer": 0.20,
    "paid": 0.15,
}

a = response.answers
score = (
    WEIGHTS["service_line"] * SERVICE_LINE_FIT[a["service_line"].choice]
    + WEIGHTS["seniority"] * SENIORITY_FIT[int(a["seniority"].score)]
    + WEIGHTS["direct_employer"] * a["direct_employer"].noul
    + WEIGHTS["paid"] * (1 - a["unpaid"].noul)
)
```

`reasons` формируются из тех же ответов — и это **лучше**, чем текст от модели:

```python
reasons = []
if a["direct_employer"].noul > 0.7:
    reasons.append("Прямой работодатель, а не перепродажа через агентство")
if a["unpaid"].noul > 0.7:
    reasons.append("Оплата только долей — денежного вознаграждения нет")
reasons.append(f"Направление: {a['service_line'].choice}")
reasons.append(f"Уровень: {a['seniority'].legend[int(a['seniority'].score)]}")
if a["text_too_thin"].noul > 0.7:
    reasons.append("Описание слишком общее — стек не указан")
```

Каждая строка — из ответа на конкретный вопрос, а не из свободного текста. Их
можно проверить, посчитать и сравнить между прогонами.

---

## Порог уверенности: где именно включается человек

Документация TypeSafe описывает это как **confidence-gated routing**: «ответ
говорит что, уверенность — стоит ли действовать».

```python
CONFIDENCE_FLOOR = 0.6

low = [name for name, ans in a.items() if ans.confidence < CONFIDENCE_FLOOR]
if low:
    # Модель сама не уверена — решает человек, а не порог.
    route_to_human_review(vacancy.id, unclear_questions=low)
```

Логика ступеней:

| Ситуация | Действие | Почему |
|----------|----------|--------|
| Любой ответ ниже 0.6 | **на ручной разбор** | модель не уверена; порог тут не поможет, он не различает «плохой лид» и «непонятная вакансия» |
| `text_too_thin` > 0.7 | **на ручной разбор** | судить не по чему; скоринг выродится в угадывание |
| `unpaid` > 0.7 | **отклонить** | не наша сделка, независимо от остального |
| `service_line = other` | **отклонить** | не наша услуга |
| Остальное | по `score` и порогу | обычный путь |

**Ключевое:** низкая уверенность — это не «плохой лид». Это «непонятная
вакансия». Смешивать их — значит терять хорошие лиды на туманных описаниях и
тратить время человека на явный мусор.

---

## Форма запроса

Транспорт — один POST. Форма ниже собрана из примера Langfuse и документации
TypeSafe; **точный эндпоинт и авторизация не проверены** `[не проверено]`.

```json
{
  "model": "jev-latest",
  "state": {
    "title": "Senior Python Developer",
    "company": "Acme",
    "description": "<полный текст вакансии>",
    "icp": "<профиль идеального клиента из TALENTFLOW_ICP_PROFILE>"
  },
  "questions": {
    "direct_employer": {
      "type": "noul",
      "instructions": "Does this vacancy text indicate that the hiring company is the direct employer — describing its own team, product or project? Answer no if the text only says the role is 'for our client' without naming the company."
    },
    "unpaid": {
      "type": "noul",
      "instructions": "Does this vacancy offer no monetary salary, compensating only with equity, revenue share, or payment deferred until funding?"
    },
    "seniority": {
      "type": "score",
      "instructions": "What seniority level does this vacancy require?",
      "criteria": ["intern or trainee", "junior", "middle", "senior", "lead, principal or head"]
    },
    "service_line": {
      "type": "choice",
      "instructions": "Which service line does this vacancy fall into, judging by the required skills and the listed responsibilities?",
      "criteria": {
        "backend": "server-side development, APIs, databases",
        "frontend": "browser or mobile user interfaces",
        "qa": "manual or automated testing",
        "devops": "infrastructure, CI/CD, cloud, SRE",
        "data": "data engineering, analytics, machine learning",
        "management": "project, product or team management",
        "other": "none of the above, or the text is too thin to tell"
      }
    },
    "text_too_thin": {
      "type": "noul",
      "instructions": "Is the vacancy description too short or too generic to identify any specific required technology or responsibility?"
    }
  }
}
```

**Про идентификаторы вопросов.** Документация подчёркивает: «Question IDs are for
your code. They are not sent to the model. Write the complete question in
`instructions`, even when the ID seems self-explanatory.» Поэтому
`"direct_employer"` — только ключ для нашего кода, а модель видит полный текст
вопроса.

---

## Почему не один вопрос со списком уровней

Можно было бы спросить `Score` из десяти уровней «насколько это хороший лид» и
не городить свёртку. Это короче, и это **хуже**:

- **Не видно, почему.** Модель вернёт позицию на шкале, но не скажет, что
  сработало — перепродажа через агентство или неподходящий уровень.
- **Нельзя взвесить по-разному.** Смена приоритета требует переписать
  формулировки уровней и заново откалибровать.
- **Смешиваются разные вещи.** «Описание туманное» и «лид плохой» — разные
  вопросы с разными действиями. В одной шкале они слипнутся.

Пять вопросов дают то же число плюс объяснение, и объяснение здесь не текст от
модели, а структура.

---

## Что нужно, чтобы это заработало

1. **Доступ к API TypeSafe.** Ключ, эндпоинт, тариф `[не проверено]` — в
   каталоге OpenRouter модель есть, но по какому пути её звать, надо уточнить
   в консоли TypeSafe.
2. **Пакет `typesafe_sdk`** — импорты в примерах выше из их документации.
3. **Замер.** Прогнать 30 размеченных вакансий и сравнить с LLM-скорингом:
   согласие с разметкой, стоимость, задержка. **Пока этого нет, экономия
   посчитана по цене, а не измерена.**
4. **Своя рубрика.** Веса в `WEIGHTS` — гипотеза. Их надо подобрать на тех же
   30 вакансиях, а не назначить на глаз.

---

## Чего этот дизайн не даёт

- **Свободного текста.** Ни письма, ни объяснения словами. Jev этого не умеет
  вовсе, и `summary` из текущего `ScoringPayload` он не заполнит.
- **Замены evals.** Jev решает, а правильно ли он решает — по-прежнему надо
  мерить разметкой.
- **Ответа на вопрос «нужен ли он нам».** Может оказаться, что расхождение с
  разметкой больше, чем у LLM, и $0.00 за выход этого не оправдают.

---

## Источники

- [TypeSafe: Primitives (Questions)](https://docs.typesafe.ai/primitives) — три типа вопросов, принципы, форма ответов
- [TypeSafe: Confidence-gated routing](https://docs.typesafe.ai/patterns/confidence-routing) — пороги и их обоснование
- [Langfuse: Using TypeSafe's Jev for evals](https://langfuse.com/blog/2026-09-18-using-typesafes-jev-for-evals) — пример запроса и ответа
- [`openrouter.ai/typesafe/jev-1.13`](https://openrouter.ai/typesafe/jev-1.13) — цена, контекст, дата релиза

---

*Составлено 23.09.2026. Спецификация, не реализация: API TypeSafe не проверялся
вживую.*

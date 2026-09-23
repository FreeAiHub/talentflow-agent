"""Application settings (env prefix: TALENTFLOW_).

Every name here is the single source of truth for what the application reads;
``.env.example`` must list exactly these and nothing more.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

#: Placeholder ICP. It is deliberately generic and MUST be replaced with the
#: real ideal-customer profile before scores mean anything commercially.
DEFAULT_ICP_PROFILE = (
    "IT-аутстафф/аутсорс компания, украинский рынок. Интересуют вакансии, "
    "которые можно закрыть нашими инженерами: разработка, QA, DevOps, данные, "
    "управление проектами. Уровень middle и выше. Прямой работодатель, а не "
    "агентство. Удалённая работа или Украина."
)

#: Placeholder sender profile. The generator may not invent achievements, so an
#: empty or generic profile here produces generic letters. Fill this in with the
#: company's real positioning and verifiable experience before sending anything.
DEFAULT_SENDER_PROFILE = (
    "IT-аутстафф компания. Собираем команды под задачи клиента: backend, "
    "frontend, QA, DevOps, data. Работаем с украинскими и европейскими "
    "клиентами. [ЗАПОЛНИТЬ: конкретные проекты, отрасли, измеримые результаты]"
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TALENTFLOW_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./talentflow.db"
    openai_api_key: str | None = None
    vapi_api_key: str | None = None
    # Response is sent only after human confirmation while True.
    human_in_the_loop: bool = True

    # --- LLM ---------------------------------------------------------------
    # OpenRouter is the gateway; Groq and Cerebras are the free fallbacks. The
    # free OpenRouter tier allows only 50 calls a day, well below what the
    # pipeline needs, so a chain rather than a single provider is the design.
    openrouter_api_key: str | None = None
    groq_api_key: str | None = None
    cerebras_api_key: str | None = None

    #: Primary model, then fallbacks in order. Comma-separated so the whole
    #: chain is one environment variable.
    llm_models: str = "openrouter:openai/gpt-oss-120b:free"
    llm_fallback_models: str = "groq:llama-3.3-70b-versatile"

    llm_timeout_seconds: float = 60.0
    llm_max_attempts: int = 3
    #: Hard ceiling on calls per UTC day. When it is reached the scorer stops
    #: and reports, rather than burning through a provider's rate limit.
    llm_daily_call_limit: int = 250
    llm_temperature: float = 0.2
    llm_max_tokens: int = 2000

    #: Used to judge whether a vacancy is worth pursuing. Replace with the real
    #: profile before trusting any score.
    icp_profile: str = DEFAULT_ICP_PROFILE

    # --- Outreach ----------------------------------------------------------
    #: Who the outreach is sent as. The generator may not invent achievements,
    #: so anything absent here is simply absent from the letter — a generic
    #: profile produces cautious, generic drafts.
    sender_profile: str = DEFAULT_SENDER_PROFILE
    #: Closing call to action. Kept out of the prompt file so the link can
    #: change without editing prose.
    cta: str = "Reply with a time that suits you."

    #: Run the fact-checking pass over every draft. Off means one fewer LLM call
    #: per draft, at the cost of possibly sending invented claims.
    grounding_check_enabled: bool = True
    #: A draft the checker calls ``reject`` must not become sendable.
    grounding_reject_is_fatal: bool = True

    # --- Pipeline ----------------------------------------------------------
    #: Off by default on purpose: an accidental `uvicorn` in development should
    #: not start hitting Djinni and spending LLM calls. Deployment turns it on.
    scheduler_enabled: bool = False
    scheduler_interval_minutes: int = 30
    #: Ceilings per run, so one sweep cannot run away with the budget.
    pipeline_parse_limit: int = 50
    pipeline_score_limit: int = 50
    #: Zero keeps drafting out of the automatic run.
    pipeline_generate_limit: int = 0
    #: Score at or above which a vacancy is worth pursuing.
    min_lead_score: float = 0.6

    # --- Notifications -----------------------------------------------------
    #: Telegram is the notification channel: free, and where the target market
    #: already lives. Absent token means notifications are simply not sent.
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    #: Sent back by Telegram in ``X-Telegram-Bot-Api-Secret-Token``. Without it
    #: the webhook is refused, so a stranger cannot approve drafts by posting.
    telegram_webhook_secret: str | None = None
    #: Ceiling on outgoing messages, to stay well clear of Telegram's limits.
    telegram_max_messages_per_minute: int = 20

    # --- Observability -----------------------------------------------------
    # Optional: traces are only sent when all three are present.
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str | None = None

    @property
    def model_chain(self) -> list[str]:
        """Primary model followed by fallbacks, in order, without blanks."""
        parts = [*self.llm_models.split(","), *self.llm_fallback_models.split(",")]
        return [part.strip() for part in parts if part.strip()]

    @property
    def telegram_enabled(self) -> bool:
        """Notifications need a token and somewhere to send them."""
        return bool(self.telegram_bot_token and self.telegram_chat_id)

    @property
    def langfuse_enabled(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()

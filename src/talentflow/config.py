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
    def langfuse_enabled(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()

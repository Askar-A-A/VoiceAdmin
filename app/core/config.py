from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    SECRET_KEY: str
    DATABASE_URL: str

    CARRIERX_ACCESS_TOKEN: str = ""
    CARRIERX_CONTAINER_SID: str = ""
    CALL_WEBHOOK_API_KEY: str = ""

    MAX_AUDIO_UPLOAD_SIZE: int = 50 * 1024 * 1024  # 50 MB

    TESTING: bool = False

    EMAIL_HOST_USER: str = ""
    EMAIL_HOST_PASSWORD: str = ""

    # CarrierX Conference v2 uses its own HTTP Basic creds (not the Bearer token).
    CARRIERX_CONF_LOGIN: str = ""
    CARRIERX_CONF_PASSWORD: str = ""

    # Free plan: the shared number callers dial before entering their access code (digits only).
    SHARED_NUMBER: str = ""
    # Voice that reads our spoken prompts (<Say>). Empty = CarrierX's default (the robotic one).
    # CarrierX accepts "man", "woman" or an Amazon Polly voice name. Language e.g. "en-US".
    TTS_VOICE: str = ""
    TTS_LANGUAGE: str = ""

    # Stripe (payments for the Private plan). Leave empty to run in demo mode:
    # without a key and a price the Upgrade button switches the plan instantly, free.
    STRIPE_SECRET_KEY: str = ""
    STRIPE_PRICE_ID: str = ""        # the recurring price of the Private plan (price_...)
    STRIPE_WEBHOOK_SECRET: str = ""  # signing secret of the webhook endpoint (whsec_...)

    # Dev only: switch the Private plan on for free, without paying. Never enable in production.
    ALLOW_FREE_UPGRADE: bool = False

    @property
    def billing_enabled(self) -> bool:
        return bool(self.STRIPE_SECRET_KEY and self.STRIPE_PRICE_ID)


settings = Settings()

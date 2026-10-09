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


settings = Settings()

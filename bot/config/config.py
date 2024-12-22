from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True)

    API_ID: int
    API_HASH: str

    USE_RANDOM_DELAY_IN_RUN: bool = True
    START_DELAY: list[int] = [30, 60]

    VANILLA_APP_ID: str = "237a903dd511477ea4d2a2019ca7c03e"
    VANILLA_SECRET_KEY: str = "550e23371cdb4012898efed9295bb9bc9139b19e-d9e648c18074fc2d83d540e1"

    AUTO_TAP: bool = True
    TAP_COUNT: list[int, int] = [80, 100]

    UPGRADE_LEVEL_WITH_SUGER: bool = False
    AUTO_TASK: bool = True

    REF_ID: str = 'inviteId10512928'

    SAVE_JS_FILES: bool = False  # Experimental `True`
    ADVANCED_ANTI_DETECTION: bool = True
    ENABLE_SSL: bool = True

    USE_PROXY_FROM_FILE: bool = False
    GIT_UPDATE_CHECKER: bool = True


settings = Settings()

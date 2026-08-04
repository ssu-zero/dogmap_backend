from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "mysql+pymysql://dogmap:dogmap@localhost:3308/dogmap"

    # 외부 API 연동 (courses 도메인 service layer에서 사용)
    KAKAO_REST_API_KEY: str = ""
    TMAP_APP_KEY: str = ""
    LLM_API_KEY: str = ""


settings = Settings()

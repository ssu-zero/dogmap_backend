from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "mysql+pymysql://dogmap:dogmap@localhost:3308/dogmap"

    # 외부 API 연동 (courses 도메인 service layer에서 사용)
    KAKAO_REST_API_KEY: str = ""
    TMAP_APP_KEY: str = ""
    LLM_API_KEY: str = ""

    # 공공데이터포털 - 반려동물 동반여행 서비스 (KorPetTourService2)
    PET_TOUR_API_KEY: str = ""
    PET_TOUR_BASE_URL: str = "https://apis.data.go.kr/B551011/KorPetTourService2"
    PET_TOUR_MOBILE_APP: str = "DogMap"


settings = Settings()

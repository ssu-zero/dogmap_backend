from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "mysql+pymysql://dogmap:dogmap@localhost:3308/dogmap"

    # 카카오 로그인 등 (courses/dogs 도메인에서 사용 예정)
    KAKAO_REST_API_KEY: str = ""

    # T맵(SK Open API) 보행자 경로 - places 도메인의 산책 코스(경유지) 계산에 사용
    TMAP_APP_KEY: str = ""
    TMAP_BASE_URL: str = "https://apis.openapi.sk.com"

    # LLM (OpenAI) - places 도메인의 장소 최종 확정에 사용
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://api.openai.com/v1"
    LLM_MODEL: str = "gpt-4o-mini"

    # 공공데이터포털 - 반려동물 동반여행 서비스 (KorPetTourService2)
    PET_TOUR_API_KEY: str = ""
    PET_TOUR_BASE_URL: str = "https://apis.data.go.kr/B551011/KorPetTourService2"
    PET_TOUR_MOBILE_APP: str = "DogMap"


settings = Settings()

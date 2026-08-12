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

    # 카카오 로그인 (OAuth2 인가 코드 방식). client_id는 KAKAO_REST_API_KEY를 그대로 쓴다
    # (카카오는 REST API 키 = OAuth client_id).
    KAKAO_CLIENT_SECRET: str = ""  # 카카오 개발자 콘솔에서 Client Secret을 활성화한 경우에만 필요
    KAKAO_REDIRECT_URI: str = "http://localhost:5173/auth/kakao/callback"

    # 자체 발급 JWT (카카오 로그인 이후 세션 유지용)
    JWT_SECRET_KEY: str = "dev-secret-change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 14  # 2주
    SIGNUP_TOKEN_EXPIRE_MINUTES: int = 30  # 신규 회원이 강아지 프로필을 입력하는 동안만 유효


settings = Settings()

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "mysql+pymysql://dogmap:dogmap@localhost:3308/dogmap"

    # 카카오 로그인 등 (courses/dogs 도메인에서 사용 예정)
    KAKAO_REST_API_KEY: str = ""

    # T맵(SK Open API) 보행자 경로 - places 도메인의 산책 코스(경유지) 계산에 사용
    TMAP_APP_KEY: str = ""
    TMAP_BASE_URL: str = "https://apis.openapi.sk.com"

    # LLM (Gemini, OpenAI 호환 엔드포인트) - places 도메인의 장소 최종 확정에 사용.
    # Gemini는 OpenAI Chat Completions와 동일한 요청/응답 형식을 지원하는 호환 엔드포인트를
    # 제공하므로(https://ai.google.dev/gemini-api/docs/openai), LLMClient 코드 변경 없이
    # base_url/model/api_key만 바꿔서 쓴다. API 키는 https://aistudio.google.com/apikey 에서 발급.
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    # 특정 버전 모델명(gemini-2.0-flash 등)은 몇 달 단위로 지원 종료된다 — 별칭을 써서
    # 모델 지원 종료 때마다 코드/설정을 바꾸지 않게 한다.
    # gemini-flash-latest는 "생각"(thinking) 모드 때문에 응답 시간이 5~30초로 들쭉날쭉했다.
    # gemini-flash-lite-latest는 실측 0.9초 안팎으로 훨씬 빠르고 일관적이라 이걸 기본값으로 쓴다
    # (장소 후보 중 선택하는 정도의 단순 작업이라 품질 차이는 거의 없었음).
    LLM_MODEL: str = "gemini-flash-lite-latest"

    # 공공데이터포털 - 반려동물 동반여행 서비스 (KorPetTourService2)
    PET_TOUR_API_KEY: str = ""
    PET_TOUR_BASE_URL: str = "https://apis.data.go.kr/B551011/KorPetTourService2"
    PET_TOUR_MOBILE_APP: str = "DogMap"

    # 카카오 로그인 (OAuth2 인가 코드 방식). client_id는 KAKAO_REST_API_KEY를 그대로 쓴다
    # (카카오는 REST API 키 = OAuth client_id).
    KAKAO_CLIENT_SECRET: str = ""  # 카카오 개발자 콘솔에서 Client Secret을 활성화한 경우에만 필요
    KAKAO_REDIRECT_URI: str = "http://localhost:5173/auth/kakao/callback"

    # 프론트엔드 도메인(쉼표로 여러 개 구분). CORSMiddleware allow_origins에 그대로 쓰인다.
    CORS_ALLOWED_ORIGINS: str = "http://localhost:5173,https://dogmap.store,https://www.dogmap.store"

    # 자체 발급 JWT (카카오 로그인 이후 세션 유지용)
    JWT_SECRET_KEY: str = "dev-secret-change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 14  # 2주
    SIGNUP_TOKEN_EXPIRE_MINUTES: int = 30  # 신규 회원이 강아지 프로필을 입력하는 동안만 유효

    # S3 (프로필 이미지 업로드 - presigned URL 방식). 버킷은 퍼블릭 읽기로 설정해서
    # image_url을 별도 서명 없이 그대로 <img src>에 쓴다. 업로드(PUT)만 presigned URL로 제한한다.
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "ap-northeast-2"
    S3_BUCKET_NAME: str = "12dogmap-images"
    S3_PRESIGNED_URL_EXPIRE_SECONDS: int = 300  # 5분 — 이 안에 PUT 업로드를 완료해야 함


settings = Settings()

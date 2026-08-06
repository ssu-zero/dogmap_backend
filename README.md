# dogmap_backend

강아지 산책 코스 추천 서비스 **DogMap**의 백엔드 API 서버입니다.

## 기술 스택

- FastAPI, SQLAlchemy 2.0, Alembic
- MySQL 8.0
- uv (패키지/가상환경 관리)

## 폴더 구조

도메인 주도(domain-driven) 구조로 구성되어 있습니다. 순환 참조를 피하기 위해 모델도 도메인별로 분리합니다.

```
app/
├── main.py                  ← FastAPI 앱, 라우터 등록
├── core/                    ← 공통 설정
│   ├── config.py            ← 환경 변수 (Settings)
│   ├── database.py          ← DB 엔진/세션
│   └── security.py          ← 인증 의존성
├── common/                  ← 도메인에 종속되지 않는 공통 코드
│   ├── base_model.py        ← SQLAlchemy Base, TimestampMixin
│   └── exceptions.py        ← 공통 예외
└── domains/
    ├── dogs/                ← 강아지 프로필
    │   ├── models.py        ← DB 테이블
    │   ├── schemas.py       ← 요청/응답 스키마
    │   ├── repository.py    ← DB 쿼리
    │   ├── service.py       ← 비즈니스 로직
    │   └── router.py        ← API 엔드포인트
    ├── courses/             ← 산책 코스, Course_Place (Kakao/T-map/LLM 연동)
    ├── places/              ← 장소, 위치(Locations)
    ├── logs/                ← 산책 기록
    ├── likes/               ← 코스 좋아요 (model/schema/repository/router)
    └── saves/               ← 코스 저장 (model/schema/repository/router)
```

`likes`, `saves`는 단순 조인 테이블이라 `service.py` 없이 `router.py`가 `repository.py`를 직접 호출합니다.

## 로컬 실행

### 1. DB 컨테이너 실행

```bash
docker compose up -d db
```

### 2. 환경 변수 설정

```bash
cp .env.example .env  # 없다면 아래 내용으로 직접 생성
```

```
DATABASE_URL=mysql+pymysql://dogmap:dogmap@localhost:3308/dogmap
```

### 3. 의존성 설치

```bash
uv sync
```

### 4. 서버 실행

```bash
uv run uvicorn app.main:app --reload
```

`http://127.0.0.1:8000/docs`에서 API 문서를 확인할 수 있습니다.

## 브랜치 전략

- **main**: 실제 배포되는 브랜치. 항상 배포 가능한 상태를 유지하며 직접 커밋/작업하지 않습니다. `develop`에서 검증된 코드만 병합합니다. push 시 GitHub Actions로 EC2에 자동 배포됩니다.
- **develop**: 개발 통합 브랜치. 모든 기능 작업은 develop을 기준으로 병합됩니다. push 및 PR 시 CI(lint, test)가 실행됩니다.
- **작업 브랜치 (feature, bug)**: 실제 개발이 이루어지는 브랜치. 작업 완료 후 PR을 통해 `develop`으로 병합합니다.

```
feature/* , bug/* → develop → main (배포)
```

### 브랜치 이름 형식

```
feature/이슈번호-작업내용
bug/이슈번호-작업내용
```

핫픽스는 이슈 제목 앞에 `🚨 [HOT]`을 붙여 우선순위를 표시합니다.

## 코드 컨벤션

Python(PEP8) 기준으로 작성합니다.

- 함수명, 변수명: `snake_case` (예: `get_dog`, `dog_id`)
- 클래스명 (모델, Pydantic 스키마, Enum 등): `PascalCase` (예: `Dog`, `DogCreate`, `DogSize`)
- 상수: `UPPER_SNAKE_CASE` (예: `MAX_COUNT`)
- Enum 멤버: `UPPER_SNAKE_CASE` (예: `DogSize.SMALL`)
- Boolean 변수/반환값 함수: `is_`, `has_`, `can_` 접두사 (예: `is_active`)
- 파일/모듈명: PEP8에 따라 `snake_case` (예: `models.py`, `discover_pet_tour_categories.py`)
- 폴더명: 내용이 드러나도록 작성 (예: `domains`, `core`, `common`)

## 커밋 컨벤션

| 작업 내용 | 코드 | 설명 |
| --- | --- | --- |
| 새로운 기능 추가 | feat | 새로운 기능 구현 |
| 버그 수정 | bug | 버그 수정 |
| 코드 리팩토링 | refactor | 코드 구조 개선 |
| 코드에 영향 없는 변경 (오타, 변수명 등) | text | 텍스트 및 리터럴 수정 |
| 주석 추가 및 수정 | comment | 주석 추가 및 수정 |
| 문서 수정 | docs | README 등 문서 수정 |
| 테스트 추가, 테스트 리팩토링 | test | 테스트 코드 작성 및 수정 |
| 빌드 or 패키지 매니저 수정 | build | 빌드, 의존성 관련 작업 |
| 파일/폴더명 추가·수정 | renamed | 리소스 이동 또는 이름 변경 |
| 파일/폴더 삭제 | delete | 불필요한 코드/파일 제거 |
| 프로젝트 시작 | init | 프로젝트를 시작했어요! |
| 설정 | chore | 설정 파일 수정 및 패키지 관리 |

## CI

- `develop` push 및 `develop`/`main` 대상 PR에서 lint(ruff) → 테스트를 실행합니다.
- `main` push 시 EC2로 자동 배포됩니다.

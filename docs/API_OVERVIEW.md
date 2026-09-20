# DogMap API 동작 방식 요약

> 작성 기준: `develop` 브랜치 (2026-08-12, PR #14 기준) + 현재 로컬 브랜치 `feature/3-courses`

## 1. 한눈에 보기

FastAPI + SQLAlchemy 2.0 + MySQL로 만든 "강아지 산책 코스 추천" 백엔드. 도메인 주도 구조(`app/domains/*`)로
나뉘어 있고, 인증은 카카오 OAuth 로그인 + 자체 발급 JWT를 쓴다. 핵심 기능은 "코스 생성" 하나이며, 이 한
요청 안에서 공공데이터 API(반려동물 동반여행 정보) → LLM(Gemini) → T맵(보행자 경로) 세 개의 외부 API를
순서대로 엮어 산책 코스를 만들어낸다.

```
[클라이언트]
   │
   ├─ POST /auth/kakao/login  ─────────────► 카카오 OAuth ─┐
   │                                                        │ access_token 또는
   │                                                        │ signup_token 발급
   ├─ POST /dogs (signup_token) ───────────► 강아지 프로필 등록, access_token 발급
   │
   └─ POST /api/v1/courses (access_token)
         │
         ├─ 1~3. 공공데이터포털 KorPetTourService2 ─ 카테고리별 후보 조회 + 상세조회 + 반려동물 동반 필터
         ├─ 4.   LLM(Gemini, OpenAI 호환 엔드포인트) ─ 후보 중 시간/카테고리 조건에 맞는 조합 확정
         └─ 5.   T맵 보행자 경로 API ─ 확정된 장소들을 순서대로 잇는 실제 도보 경로/거리/시간 계산
               │
               └─► DB(Course/CoursePlace)에 저장 후 응답
```

## 2. 인증 흐름

- **카카오 로그인** `POST /auth/kakao/login`: 프론트가 카카오 인가 코드(`code`)를 넘기면, 서버가 그 코드로
  카카오 access token → 사용자 정보를 조회한다 ([kakao_client.py](../app/domains/auth/external/kakao_client.py), [service.py](../app/domains/auth/service.py)).
  - 기존 회원(kakao_id로 조회됨) → `status=LOGIN` + 서비스용 `access_token` 반환.
  - 신규 회원 → `status=SIGNUP_REQUIRED` + `signup_token` 반환 (강아지 프로필 입력 전까지만 유효, 30분).
- **온보딩** `POST /dogs` (Authorization: `signup_token`): 강아지 프로필을 등록하면 그 시점에 진짜
  `access_token`(2주 유효)을 발급한다.
- 이후 모든 API는 `Authorization: Bearer {access_token}` 헤더로 인증한다. JWT는 자체 서명(HS256,
  `JWT_SECRET_KEY`)이며 payload의 `type` 클레임으로 `access`/`signup` 토큰을 구분한다
  ([security.py](../app/core/security.py)).
- 코스 목록/상세 조회처럼 비로그인도 허용하되 로그인 시 소유자 여부(`is_owner`)를 알아야 하는 API는
  `get_current_dog_id_optional`로 토큰이 없으면 `None`, 있는데 무효하면 401을 낸다.

## 3. 코스 생성 파이프라인 (핵심 로직)

`POST /api/v1/courses` 한 번 호출로 아래 5단계가 순서대로 실행된다 ([places/service.py](../app/domains/places/service.py)).

| 단계 | 내용 | 외부 API |
| --- | --- | --- |
| 1~3 | 카테고리(식당/카페/산책/액티비티)별로 위치 기반 후보를 조회 → 후보마다 상세조회 3종(intro/petTour/common) 병렬 호출 → `acmpyPsblCpam`(동반 가능 반려동물) 값이 있는 곳만 필터링 | 공공데이터포털 `KorPetTourService2` |
| 4 | 필터를 통과한 후보 전체 + 사용자가 지정한 카테고리별 목표 개수 + 목표 산책시간을 LLM에 넘겨, 시간 예산(목표시간의 약 70%)에 맞는 조합을 JSON으로 선택받음 | Gemini (`LLM_BASE_URL`, OpenAI Chat Completions 호환 스펙) |
| 5 | 확정된 장소들을 방문 순서대로 T맵 보행자 경로 API에 한 번에 넘겨(`passList`로 다중 경유지 지원) 구간별 거리/시간과 전체 폴리라인을 계산 | T맵(SK Open API) 보행자 경로 |

- 3단계까지 공공데이터 API 실패율이 50%를 넘으면 `PlaceCandidateServiceUnavailable`로 즉시 502를 반환한다.
- 후보가 목표 개수보다 적으면 반경을 2배씩 넓혀 최대 1회 재시도하고, 그래도 부족하면 있는 만큼만 사용한다.
- 실제 이동 순서 재계산 없이 LLM이 고른 순서를 그대로 T맵 경유지 순서로 사용한다.
- 완성된 결과는 `Course`/`CoursePlace` 테이블에 저장되고, 조회 시(`GET /courses/{id}`)에는 T맵을 다시
  부르지 않고 저장된 `path`와 `CoursePlace` 합산값으로만 응답을 구성한다.

## 4. 주요 엔드포인트

| 메서드 | 경로 | 인증 | 설명 |
| --- | --- | --- | --- |
| POST | `/auth/kakao/login` | 없음 | 카카오 인가 코드로 로그인/신규가입 분기 |
| POST | `/dogs` | signup_token | 강아지 프로필 등록 = 회원가입 완료 |
| GET | `/dogs/me` | access_token | 내 프로필 조회 |
| PATCH | `/dogs/me` | access_token | 내 프로필 부분 수정 |
| GET | `/api/v1/courses` | 선택 | 반경 내 공개 코스 목록 (거리순) |
| POST | `/api/v1/courses` | access_token | 코스 생성 (위 5단계 파이프라인 실행) |
| GET | `/api/v1/courses/{id}` | 선택 | 코스 상세 (비공개는 소유자만, 그 외 404) |
| POST | `/api/v1/courses/{id}/share` | access_token | 코스 전체 공개 전환 (소유자만, idempotent) |
| DELETE | `/api/v1/courses/{id}` | access_token | 코스 삭제 (소유자만) |
| GET | `/health` | 없음 | 헬스체크 |

`likes`(좋아요), `saves`(저장), `logs`(산책 기록) 도메인은 현재 DB 모델(`models.py`)만 존재하고
router/schema/repository는 아직 구현되어 있지 않아 API로 노출되지 않는다.

## 5. 외부 연동 요약

| 연동 | 용도 | 설정 |
| --- | --- | --- |
| 카카오 OAuth | 로그인 | `KAKAO_REST_API_KEY`, `KAKAO_CLIENT_SECRET`, `KAKAO_REDIRECT_URI` |
| 공공데이터포털 KorPetTourService2 | 반려동물 동반 가능 장소 후보 | `PET_TOUR_API_KEY` |
| 카카오 OAuth | 로그인 | `KAKAO_REST_API_KEY`, `KAKAO_CLIENT_SECRET`, `KAKAO_REDIRECT_URI`, `KAKAO_ALLOWED_REDIRECT_URIS` |
| Gemini (OpenAI 호환) | 최종 장소 조합 선택(LLM) | `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL=gemini-flash-lite-latest` (thinking 없는 lite 모델을 응답속도 때문에 기본값으로 사용) |
| T맵(SK Open API) | 보행자 경로/거리/시간 계산 | `TMAP_APP_KEY` |
| 자체 JWT | 세션 유지 | `JWT_SECRET_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES`(2주), `SIGNUP_TOKEN_EXPIRE_MINUTES`(30분) |

## 6. 배포 구조

- **CI** (`.github/workflows/ci.yml`): `develop` push, `develop`/`main` 대상 PR에서 ruff lint → pytest 실행.
- **CD** (`.github/workflows/deploy.yml`): **`main` 브랜치에 push되는 순간** GitHub Actions가 SSH로
  EC2(`secrets.EC2_HOST`)에 접속해 `git pull origin main` → `.env`에 `DATABASE_URL` 주입 →
  `docker compose down && docker compose up --build -d` 를 실행한다. 즉 배포는 "main에 머지"가 곧
  트리거이며, 별도의 배포 승인 단계는 없다.
- 브랜치 전략: `feature/* , bug/* → develop → main(배포)`. develop은 CI만 돌고 실제 배포에는 영향 없음.

## 7. 지금 실제로 배포되어 있는지 (결론)

**아니오 — EC2에는 초기 스켈레톤만 배포되어 있고, 카카오 로그인/강아지 프로필/코스 생성 같은 실제 기능은
아직 배포되어 있지 않습니다.**

근거 (GitHub `ssu-zero/dogmap_backend` 저장소 확인):

- `main` 브랜치의 최신 커밋은 `cb907e8` (`Merge pull request #1 from ssu-zero/develop`, 2026-08-04) 하나뿐이고,
  이 PR의 내용은 "도메인 폴더 구조 설정, 템플릿 작성" — 즉 `domains/` 뼈대와 이슈/PR 템플릿, CI 설정 정도다.
- 실제 기능이 담긴 PR들은 전부 **`develop`을 base로** 머지됐고 `main`에는 아직 반영되지 않았다:
  - PR #10 `장소 추출 api 구현` (2026-08-06, → develop)
  - PR #11 `onboarding, kakao oauth 구현` (2026-08-12, → develop)
  - PR #13 `마이페이지 수정 api` (2026-08-12, → develop)
  - PR #14 `코스 api 구현` (2026-08-12, → develop)
- `Deploy to EC2` 워크플로우는 지금까지 **딱 2번** 실행됐고 둘 다 그 초기 스켈레톤 커밋들에 대한 것이다
  (2026-07-22, 2026-08-04). PR #10/#11/#13/#14가 머지된 이후로 `main` push가 없었으므로 배포도 다시
  일어나지 않았다.
- 따라서 지금 EC2에서 떠 있는 컨테이너는 `/health`와 텅 빈 라우터 정도만 응답할 뿐, 이 문서의 3~4장에서
  설명한 카카오 로그인/코스 생성 API는 아직 서버에 존재하지 않을 가능성이 높다.

**다음 배포를 하려면**: `develop → main` PR을 만들어 머지하면 그 즉시 `deploy.yml`이 실행되어 EC2에
현재 `develop`(사실상 모든 기능 포함) 상태가 배포된다.

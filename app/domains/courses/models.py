from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.base_model import Base, TimestampMixin

if TYPE_CHECKING:
    from app.domains.dogs.models import Dog
    from app.domains.places.models import Place


class Course(TimestampMixin, Base):
    __tablename__ = "courses"

    course_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)

    # 코스를 만든 회원. 회원 탈퇴 후에도 코스(및 다른 회원의 좋아요/저장/기록)는 남기기
    # 위해 ondelete="SET NULL" — Log.course_id와 대칭되는 패턴.
    dog_id: Mapped[int | None] = mapped_column(
        ForeignKey("dogs.dog_id", ondelete="SET NULL"), nullable=True, index=True
    )
    dog: Mapped["Dog | None"] = relationship()

    # 기본 비공개. 소유자가 공유 API를 호출해야 주변 코스 목록 등 공개 조회에 노출된다.
    is_shared: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # 시작 좌표는 다른 테이블을 참조하지 않는, Course 자체의 일반 값 컬럼이다.
    start_lat: Mapped[float] = mapped_column(Float, nullable=False)
    start_lng: Mapped[float] = mapped_column(Float, nullable=False)

    # 산책을 시작할 예정 일시. CoursePlace.visit_time은 이 값에 구간별
    # travel_minutes/stay_minutes를 누적해서 계산하며 별도로 저장하지 않는다
    # (courses/router.py 참고). API 레벨에서는 필수지만, 과거 방식으로 만들어진
    # 행과의 호환을 위해 컬럼 자체는 nullable로 둔다.
    walk_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # 생성 시 T맵 응답으로 받은 전체 폴리라인을 [[lat, lng], ...] 형태로 저장한다.
    # 상세조회 시 T맵을 다시 호출하지 않고 그대로 재사용하기 위함.
    path: Mapped[list | None] = mapped_column(JSON, nullable=True)

    def touch(self) -> None:
        """CoursePlace 등 자식 엔티티만 바뀌어 Course 행 자체엔 UPDATE가 없을 때,
        코스 구성 변경을 Course 수정으로 간주하려면 서비스 계층에서 이 메서드를 호출한다.
        """
        self.updated_at = datetime.now(UTC)


class CoursePlace(TimestampMixin, Base):
    """Course와 Place를 연결하는 단순 조인 테이블이 아니라, 방문 순서/체류 시간/이동 시간·거리를
    가지는 독립 엔티티. course_id+place_id 복합 PK를 쓰지 않는 이유는 한 코스 안에서 같은
    장소를 두 번 방문하는 경로(예: 공원 입구 → 카페 → 공원 입구)를 표현하기 위함이다.
    """

    __tablename__ = "course_places"

    __table_args__ = (
        UniqueConstraint("course_id", "sequence", name="uq_course_places_course_sequence"),
        # 같은 장소를 한 코스에서 중복 방문할 수 없다는 정책이 확정되면 아래를 추가한다:
        # UniqueConstraint("course_id", "place_id", name="uq_course_places_course_place"),
    )

    course_place_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.course_id", ondelete="CASCADE"), nullable=False, index=True
    )
    course: Mapped["Course"] = relationship()

    place_id: Mapped[int] = mapped_column(
        ForeignKey("places.place_id", ondelete="RESTRICT"), nullable=False, index=True
    )
    place: Mapped["Place"] = relationship()

    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    stay_minutes: Mapped[int | None] = mapped_column(Integer)
    travel_minutes: Mapped[int | None] = mapped_column(Integer)
    travel_distance_meters: Mapped[int | None] = mapped_column(Integer)

import enum
from datetime import time

from sqlalchemy import BigInteger, Enum, Float, String, Text, Time
from sqlalchemy.orm import Mapped, mapped_column

from app.common.base_model import Base, TimestampMixin


class PlaceCategory(str, enum.Enum):
    """TODO: 실제 카테고리 목록은 기획 확정 후 조정."""

    PARK = "PARK"
    CAFE = "CAFE"
    RESTAURANT = "RESTAURANT"
    HOSPITAL = "HOSPITAL"
    PET_SHOP = "PET_SHOP"
    ETC = "ETC"


class Place(TimestampMixin, Base):
    """장소. 위도/경도는 Place 자체의 값으로 보유한다 (별도 Location 엔티티 없음) —
    한 Place에 좌표 하나만 대응되고 좌표를 독립적으로 생성/조회/수정할 요구사항이
    없다면 별도 테이블로 분리하는 건 과도한 설계라 통합했다.
    """

    __tablename__ = "places"

    place_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # 공공데이터(KorPetTourService2) content_id — 코스 생성 파이프라인이 같은 장소를
    # 여러 코스에서 재사용할 때 이 값으로 get-or-create해서 Place row 중복 생성을 막는다.
    content_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str | None] = mapped_column(Text)
    category: Mapped[PlaceCategory] = mapped_column(
        Enum(PlaceCategory, name="place_category"), nullable=False
    )
    image_url: Mapped[str | None] = mapped_column(String(500))
    # TODO: 영업시간이 보통 "시작~종료" 범위인데 단일 Time 컬럼이라 표현이 제한적이다.
    # 필요해지면 open_time/close_time 쌍으로 분리 검토.
    open_time: Mapped[time | None] = mapped_column(Time)
    rest_day: Mapped[str | None] = mapped_column(String(100))

    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)

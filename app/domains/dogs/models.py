import enum

from sqlalchemy import BigInteger, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.common.base_model import Base, TimestampMixin


class DogSize(str, enum.Enum):
    """온보딩 화면 기준: 소형 10kg 이하 / 중형 10~25kg / 대형 25kg 이상."""

    SMALL = "SMALL"
    MEDIUM = "MEDIUM"
    LARGE = "LARGE"


class Dog(TimestampMixin, Base):
    """강아지 프로필이자 회원 엔티티.

    이 서비스는 별도의 User/OAuthAccount 테이블을 두지 않는다. 카카오 로그인 후
    반려견 정보를 입력하는 시점에 회원 1명과 반려견 프로필 1개가 동일한 Dogs
    레코드로 생성되며, 이후 내부 도메인 간 참조(Log/Like/Save 등)는 전부 이
    dog_id를 회원 식별자로 사용한다. kakao_id는 로그인 시 기존 회원을 찾을 때만 쓴다.
    """

    __tablename__ = "dogs"

    dog_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # 카카오에서 전달받은 외부 사용자 식별값. 다른 테이블을 참조하는 FK가 아니다
    # (별도 카카오 계정 테이블을 두지 않으므로 ForeignKey/relationship 대상이 없음).
    kakao_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True, index=True)

    image_url: Mapped[str | None] = mapped_column(String(500))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    age: Mapped[int | None] = mapped_column(Integer)
    size: Mapped[DogSize] = mapped_column(Enum(DogSize, name="dog_size"), nullable=False)

import enum
from typing import TYPE_CHECKING

from sqlalchemy import Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.base_model import Base, TimestampMixin

if TYPE_CHECKING:
    from app.domains.likes.models import Like
    from app.domains.logs.models import Log
    from app.domains.saves.models import Save


class DogSize(str, enum.Enum):
    """TODO: 실제 사이즈 구간 기준은 기획 확정 후 조정."""

    SMALL = "SMALL"
    MEDIUM = "MEDIUM"
    LARGE = "LARGE"


class Dog(TimestampMixin, Base):
    __tablename__ = "dogs"

    dog_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    image_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    weight: Mapped[int] = mapped_column(Integer, nullable=False)
    size: Mapped[DogSize] = mapped_column(Enum(DogSize), nullable=False)
    kakao_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    logs: Mapped[list["Log"]] = relationship(
        "Log", back_populates="dog", cascade="all, delete-orphan"
    )
    likes: Mapped[list["Like"]] = relationship(
        "Like", back_populates="dog", cascade="all, delete-orphan"
    )
    saves: Mapped[list["Save"]] = relationship(
        "Save", back_populates="dog", cascade="all, delete-orphan"
    )

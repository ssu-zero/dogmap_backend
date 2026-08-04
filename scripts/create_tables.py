"""스키마가 안정화되기 전까지 Alembic 마이그레이션 대신 사용하는 임시 스크립트.

스키마 변경 시 테이블을 지우고 다시 실행해서 최신 모델 상태로 맞춘다.
"""

from app.common.base_model import Base
from app.core.database import engine
from app.domains.courses import models as courses_models  # noqa: F401
from app.domains.dogs import models as dogs_models  # noqa: F401
from app.domains.likes import models as likes_models  # noqa: F401
from app.domains.logs import models as logs_models  # noqa: F401
from app.domains.places import models as places_models  # noqa: F401
from app.domains.saves import models as saves_models  # noqa: F401

if __name__ == "__main__":
    Base.metadata.create_all(engine)
    print("Tables created:", sorted(Base.metadata.tables.keys()))

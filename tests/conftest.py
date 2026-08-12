"""SQLite에서 BigInteger PK도 autoincrement(rowid-alias)로 동작하게 만든다.

SQLite는 PK 컬럼이 정확히 "INTEGER" 타입일 때만 rowid-alias autoincrement가 동작한다
(BigInteger는 BIGINT로 컴파일되어 이 규칙에 해당하지 않음 — tests/test_model_constraints.py
상단 설명 참고). 실제 서비스 코드(repository 계층)는 PK를 직접 지정하지 않고 DB의
autoincrement에 의존하므로, 테스트에서 이를 그대로 재현하려면 SQLite에서만 BigInteger를
INTEGER로 컴파일하도록 만들어야 한다. 실제 MySQL 컴파일에는 영향 없음.
"""

from sqlalchemy import BigInteger
from sqlalchemy.ext.compiler import compiles


@compiles(BigInteger, "sqlite")
def _compile_big_integer_as_integer_for_sqlite(type_, compiler, **kw):
    return "INTEGER"

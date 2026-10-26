from sqlalchemy.pool import QueuePool

from app.database import build_engine


def test_postgresql_engine_uses_bounded_pre_ping_pool_without_connecting():
    engine = build_engine(
        "postgresql+psycopg://user:synthetic-password@127.0.0.1/coordination?sslmode=require",
        pool_size=2,
        max_overflow=3,
        pool_timeout=7,
        pool_recycle=600,
    )
    try:
        assert engine.dialect.name == "postgresql"
        assert isinstance(engine.pool, QueuePool)
        assert engine.pool.size() == 2
        assert engine.pool._max_overflow == 3
        assert engine.pool._timeout == 7
        assert engine.pool._recycle == 600
        assert engine.pool._pre_ping is True
    finally:
        engine.dispose()

from logging.config import fileConfig

from alembic import context
from alembic.script.base import Script
from sqlalchemy import engine_from_config, pool

from app.config import get_settings
from app.database import Base
from app.migration_lock import acquire_alembic_migration_lock
from app import models  # noqa: F401

# macOS external volumes can leave AppleDouble sidecars beside Python files.
# Alembic's default revision scanner accepts their `._*.py` names as scripts,
# then fails while decoding their binary resource-fork contents.
_list_py_dir = Script._list_py_dir


def _list_python_migrations(cls, scriptdir, path):
    return [item for item in _list_py_dir(scriptdir, path) if not item.name.startswith("._")]


Script._list_py_dir = classmethod(_list_python_migrations)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
config.set_main_option("sqlalchemy.url", get_settings().database_url)
target_metadata = Base.metadata


def run_migrations_offline():
    context.configure(url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata,
                      literal_binds=True, dialect_opts={"paramstyle": "named"}, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(config.get_section(config.config_ini_section, {}),
                                     prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            # PostgreSQL's outer Alembic transaction remains active through
            # run_migrations() with the default transaction_per_migration=False.
            # Acquire before Alembic reads the database's current revision.
            acquire_alembic_migration_lock(connection)
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

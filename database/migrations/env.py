from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.core.config import settings
from app.db.base import Base
from app.integrations.employer_portal import models as employer_portal_models  # noqa: F401
from app.integrations.hamis import models as hamis_models  # noqa: F401
from app.modules.cv_parser import models as cv_parser_models  # noqa: F401
from app.modules.demand import models as demand_models  # noqa: F401
from app.modules.external_references import models as reference_models  # noqa: F401
from app.modules.iam import models as iam_models  # noqa: F401
from app.modules.marketing import models as marketing_models  # noqa: F401
from app.modules.matching import models as matching_models  # noqa: F401
from app.modules.merl import models as merl_models  # noqa: F401
from app.modules.placement import models as placement_models  # noqa: F401
from app.modules.reporting import models as reporting_models  # noqa: F401
from app.modules.supply import models as supply_models  # noqa: F401
from app.modules.training import models as training_models  # noqa: F401
from app.modules.work import models as work_models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(settings.database_url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

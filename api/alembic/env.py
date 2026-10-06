from alembic import context

from vesper import models  # noqa: F401  registers tables
from vesper.db import Base, engine


def run() -> None:
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()


run()

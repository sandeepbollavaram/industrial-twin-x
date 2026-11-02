from alembic import context
from sqlalchemy import create_engine
from twinx_api.db import Base
from twinx_api.settings import Settings

engine = create_engine(Settings().database_url)
with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()

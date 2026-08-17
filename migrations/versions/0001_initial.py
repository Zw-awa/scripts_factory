"""Initial world-model schema.

Revision ID: 0001
Revises: None
"""
from alembic import op

from scripts_factory.database import initialize_database
from scripts_factory.models import Base

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    initialize_database(op.get_bind().engine)


def downgrade() -> None:
    bind = op.get_bind()
    bind.exec_driver_sql("DROP TABLE IF EXISTS memory_fts")
    Base.metadata.drop_all(bind)

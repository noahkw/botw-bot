"""make CommandLog._guild nullable

Revision ID: 56aa9ca0c127
Revises: 33ab173d34a2
Create Date: 2021-03-31 06:57:26.672776

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "56aa9ca0c127"
down_revision = "33ab173d34a2"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("command_logs", "_guild", existing_type=sa.BIGINT(), nullable=True)


def downgrade():
    op.alter_column("command_logs", "_guild", existing_type=sa.BIGINT(), nullable=False)

"""add GuildSettings.whitelisted

Revision ID: 099219c215b9
Revises:
Create Date: 2020-11-14 20:30:12.644563

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "099219c215b9"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "guild_settings", sa.Column("whitelisted", sa.Boolean(), nullable=True)
    )


def downgrade():
    op.drop_column("guild_settings", "whitelisted")

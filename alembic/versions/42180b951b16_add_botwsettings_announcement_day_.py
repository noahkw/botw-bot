"""add BotWSettings.announcement_day; BotWSettings.winner_day

Revision ID: 42180b951b16
Revises: 099219c215b9
Create Date: 2020-11-29 18:05:11.654053

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "42180b951b16"
down_revision = "099219c215b9"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "botw_settings", sa.Column("announcement_day", sa.Integer(), nullable=True)
    )
    op.add_column("botw_settings", sa.Column("winner_day", sa.Integer(), nullable=True))

    # populate with previous global default values
    op.execute("UPDATE botw_settings SET announcement_day = 0 WHERE true;")
    op.execute("UPDATE botw_settings SET winner_day = 3 WHERE true;")

    # alter the columns to be non-nullable
    op.alter_column("botw_settings", "announcement_day", nullable=False)
    op.alter_column("botw_settings", "winner_day", nullable=False)


def downgrade():
    op.drop_column("botw_settings", "winner_day")
    op.drop_column("botw_settings", "announcement_day")

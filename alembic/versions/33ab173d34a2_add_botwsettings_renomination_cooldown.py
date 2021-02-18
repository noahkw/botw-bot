"""add BotwSettings.renomination_cooldown

Revision ID: 33ab173d34a2
Revises: 42180b951b16
Create Date: 2021-02-19 00:00:34.097366

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "33ab173d34a2"
down_revision = "42180b951b16"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "botw_settings", sa.Column("renomination_cooldown", sa.Integer(), nullable=True)
    )


def downgrade():
    op.drop_column("botw_settings", "renomination_cooldown")

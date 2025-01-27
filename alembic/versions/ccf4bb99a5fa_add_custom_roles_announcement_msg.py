"""add custom roles announcement msg

Revision ID: ccf4bb99a5fa
Revises: 70798f0b4c85
Create Date: 2025-01-27 22:00:04.504002

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "ccf4bb99a5fa"
down_revision = "70798f0b4c85"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "custom_role_settings",
        sa.Column("_announcement_message", sa.String(), nullable=True),
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("custom_role_settings", "_announcement_message")
    # ### end Alembic commands ###

"""Add RoleSettings

Revision ID: a632afbaf331
Revises: 56aa9ca0c127
Create Date: 2022-02-13 02:08:15.691809

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a632afbaf331"
down_revision = "56aa9ca0c127"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "role_settings",
        sa.Column("_guild", sa.BigInteger(), nullable=False),
        sa.Column("_auto_role", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("_guild"),
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("role_settings")
    # ### end Alembic commands ###
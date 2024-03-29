"""Add GuildCogs model

Revision ID: b6fdae5a4a5a
Revises: a632afbaf331
Create Date: 2022-11-27 14:07:23.675070

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b6fdae5a4a5a"
down_revision = "a632afbaf331"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "guild_cogs",
        sa.Column("_guild", sa.BigInteger(), nullable=False),
        sa.Column("cog", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("_guild", "cog"),
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("guild_cogs")
    # ### end Alembic commands ###

"""add banned words model

Revision ID: 70798f0b4c85
Revises: 2f49c0729ee4
Create Date: 2024-02-04 21:08:17.032065

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "70798f0b4c85"
down_revision = "2f49c0729ee4"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "banned_words",
        sa.Column("_banned_word", sa.Integer(), nullable=False),
        sa.Column("word", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("_banned_word"),
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("banned_words")
    # ### end Alembic commands ###
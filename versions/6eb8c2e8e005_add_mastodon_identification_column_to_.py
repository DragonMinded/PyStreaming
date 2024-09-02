"""Add mastodon identification column to streamer table.

Revision ID: 6eb8c2e8e005
Revises: 15b58cab2cbb
Create Date: 2024-09-02 19:41:46.774016

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6eb8c2e8e005'
down_revision = '15b58cab2cbb'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('streamersettings', sa.Column('mastodon', sa.String(length=256), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('streamersettings', 'mastodon')
    # ### end Alembic commands ###

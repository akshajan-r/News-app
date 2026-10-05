"""Widen password_hash and article URL columns

Werkzeug's scrypt password hashes are ~162 characters, longer than the
original 128-character column. SQLite ignores VARCHAR lengths so this only
fails on Postgres, where it breaks sign-up. Article URLs come from whatever
link is being read and can run past 500 characters.

Revision ID: c7d2a91e4f10
Revises: 3db8b6fc7571
Create Date: 2026-10-05 19:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c7d2a91e4f10'
down_revision = '3db8b6fc7571'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.alter_column('password_hash',
                              existing_type=sa.String(length=128),
                              type_=sa.String(length=256),
                              existing_nullable=False)

    with op.batch_alter_table('read_article', schema=None) as batch_op:
        batch_op.alter_column('article_url',
                              existing_type=sa.String(length=500),
                              type_=sa.String(length=2048),
                              existing_nullable=False)

    with op.batch_alter_table('article_view', schema=None) as batch_op:
        batch_op.alter_column('article_url',
                              existing_type=sa.String(length=500),
                              type_=sa.String(length=2048),
                              existing_nullable=False)


def downgrade():
    with op.batch_alter_table('article_view', schema=None) as batch_op:
        batch_op.alter_column('article_url',
                              existing_type=sa.String(length=2048),
                              type_=sa.String(length=500),
                              existing_nullable=False)

    with op.batch_alter_table('read_article', schema=None) as batch_op:
        batch_op.alter_column('article_url',
                              existing_type=sa.String(length=2048),
                              type_=sa.String(length=500),
                              existing_nullable=False)

    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.alter_column('password_hash',
                              existing_type=sa.String(length=256),
                              type_=sa.String(length=128),
                              existing_nullable=False)

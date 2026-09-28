"""idle expiry for repositories

Revision ID: 4c1f7a2be910
Revises: b0f10bad96ec
Create Date: 2026-09-28

Three changes, in this order because each depends on the one before it:

1. `repositories.last_accessed_at`, backfilled from `created_at`. Without a
   backfill every existing repository reads as "never accessed" and the first
   sweep deletes all of them.
2. Delete orphaned chunks. `code_chunks.repository_id` had no foreign key, so
   chunks whose repository row is already gone are unreachable and would
   otherwise be kept forever.
3. The foreign key itself, with ON DELETE CASCADE, so deleting a repository
   from any path in the future cannot leak another copy of step 2.
"""

from alembic import op
import sqlalchemy as sa

revision = "4c1f7a2be910"
down_revision = "b0f10bad96ec"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "repositories",
        sa.Column("last_accessed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        "UPDATE repositories SET last_accessed_at = created_at "
        "WHERE last_accessed_at IS NULL"
    )
    # The column is NOT NULL in the model; existing rows are backfilled above.
    op.alter_column(
        "repositories",
        "last_accessed_at",
        nullable=False,
        server_default=sa.func.now(),
    )
    op.create_index(
        "ix_repositories_last_accessed_at",
        "repositories",
        ["last_accessed_at"],
    )

    op.execute(
        "DELETE FROM code_chunks WHERE repository_id NOT IN (SELECT id FROM repositories)"
    )
    op.create_foreign_key(
        "fk_code_chunks_repository_id",
        "code_chunks",
        "repositories",
        ["repository_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade():
    op.drop_constraint(
        "fk_code_chunks_repository_id", "code_chunks", type_="foreignkey"
    )
    op.drop_index("ix_repositories_last_accessed_at", table_name="repositories")
    op.drop_column("repositories", "last_accessed_at")

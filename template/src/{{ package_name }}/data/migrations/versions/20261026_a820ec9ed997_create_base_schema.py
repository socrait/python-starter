"""create base schema

Revision ID: a820ec9ed997
Revises:
Create Date: 2026-10-26 19:44:56.505224+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a820ec9ed997"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "org",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_org")),
    )
    with op.batch_alter_table("org", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_org_created_at"), ["created_at"], unique=False)
        batch_op.create_index(batch_op.f("ix_org_updated_at"), ["updated_at"], unique=False)

    op.create_table(
        "user_account",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_account")),
        sa.UniqueConstraint("email", name=op.f("uq_user_account_email")),
    )
    with op.batch_alter_table("user_account", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_user_account_created_at"), ["created_at"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_user_account_updated_at"), ["updated_at"], unique=False
        )

    op.create_table(
        "membership",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("org_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column(
            "role",
            sa.Enum("member", "admin", name="role", native_enum=False, length=32),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["org_id"], ["org.id"], name=op.f("fk_membership_org_id_org"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user_account.id"],
            name=op.f("fk_membership_user_id_user_account"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_membership")),
    )
    with op.batch_alter_table("membership", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_membership_created_at"), ["created_at"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_membership_org_id_user_id"),
            ["org_id", "user_id"],
            unique=True,
            postgresql_where=sa.text("deleted_at IS NULL"),
            sqlite_where=sa.text("deleted_at IS NULL"),
        )
        batch_op.create_index(batch_op.f("ix_membership_updated_at"), ["updated_at"], unique=False)

    op.create_table(
        "project",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("org_id", sa.String(), nullable=False),
        sa.Column("owner_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["org_id"], ["org.id"], name=op.f("fk_project_org_id_org"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["user_account.id"], name=op.f("fk_project_owner_id_user_account")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_project")),
    )
    with op.batch_alter_table("project", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_project_created_at"), ["created_at"], unique=False)
        batch_op.create_index(batch_op.f("ix_project_org_id"), ["org_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_project_owner_id"), ["owner_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_project_updated_at"), ["updated_at"], unique=False)

    op.create_table(
        "task",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("org_id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("open", "done", name="taskstatus", native_enum=False, length=32),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["org_id"], ["org.id"], name=op.f("fk_task_org_id_org"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["project.id"],
            name=op.f("fk_task_project_id_project"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_task")),
    )
    with op.batch_alter_table("task", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_task_created_at"), ["created_at"], unique=False)
        batch_op.create_index(batch_op.f("ix_task_org_id"), ["org_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_task_project_id"), ["project_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_task_updated_at"), ["updated_at"], unique=False)

    op.create_table(
        "task_assignee",
        sa.Column("task_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["task_id"], ["task.id"], name=op.f("fk_task_assignee_task_id_task"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user_account.id"],
            name=op.f("fk_task_assignee_user_id_user_account"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("task_id", "user_id", name=op.f("pk_task_assignee")),
    )
    with op.batch_alter_table("task_assignee", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_task_assignee_user_id"), ["user_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("task_assignee", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_task_assignee_user_id"))

    op.drop_table("task_assignee")
    with op.batch_alter_table("task", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_task_updated_at"))
        batch_op.drop_index(batch_op.f("ix_task_project_id"))
        batch_op.drop_index(batch_op.f("ix_task_org_id"))
        batch_op.drop_index(batch_op.f("ix_task_created_at"))

    op.drop_table("task")
    with op.batch_alter_table("project", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_project_updated_at"))
        batch_op.drop_index(batch_op.f("ix_project_owner_id"))
        batch_op.drop_index(batch_op.f("ix_project_org_id"))
        batch_op.drop_index(batch_op.f("ix_project_created_at"))

    op.drop_table("project")
    with op.batch_alter_table("membership", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_membership_updated_at"))
        batch_op.drop_index(
            batch_op.f("ix_membership_org_id_user_id"),
            postgresql_where=sa.text("deleted_at IS NULL"),
            sqlite_where=sa.text("deleted_at IS NULL"),
        )
        batch_op.drop_index(batch_op.f("ix_membership_created_at"))

    op.drop_table("membership")
    with op.batch_alter_table("user_account", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_user_account_updated_at"))
        batch_op.drop_index(batch_op.f("ix_user_account_created_at"))

    op.drop_table("user_account")
    with op.batch_alter_table("org", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_org_updated_at"))
        batch_op.drop_index(batch_op.f("ix_org_created_at"))

    op.drop_table("org")

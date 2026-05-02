"""DB-driven RBAC: permissions, role_permissions, user_roles, user_permissions
(doc 21 part B).

Tables:
  - permissions(code PK, name, description, is_builtin, created_at, updated_at)
  - role_permissions(role_id, permission_code) composite PK
  - user_roles(user_id, role_id) composite PK
  - user_permissions(user_id, permission_code) composite PK

Data migration:
  - Drops the legacy ``roles.permissions`` JSON column (replaced by the join
    table). Existing role rows lose their JSON list — re-seeded via the
    startup sync against the in-code registry.
  - Drops ``users.admin`` boolean column. Before the drop, every user with
    ``admin=True`` is assigned to the seeded ``admin`` role (created here
    if absent). Superuser status is now membership-based.

The startup sync (RbacRepository.sync_builtin_permissions) re-seeds the
permission catalog and the admin role's permission set on every boot;
this migration only ensures the schema is in place and existing admin
users keep their privileges across the cutover.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-02
"""
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String


revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---- New tables --------------------------------------------------------
    op.create_table(
        "permissions",
        Column("code", String(length=128), primary_key=True),
        Column("name", String(length=255), nullable=False),
        Column("description", String(length=1024), nullable=True),
        Column("is_builtin", Boolean, nullable=False, server_default=sa.false()),
        Column("created_at", DateTime, nullable=False),
        Column("updated_at", DateTime, nullable=False),
    )

    op.create_table(
        "role_permissions",
        Column("role_id", Integer, ForeignKey("roles.id"), primary_key=True),
        Column(
            "permission_code",
            String(length=128),
            ForeignKey("permissions.code"),
            primary_key=True,
        ),
        Column("created_at", DateTime, nullable=False),
    )
    op.create_index("idx_role_permissions_role", "role_permissions", ["role_id"])
    op.create_index(
        "idx_role_permissions_permission", "role_permissions", ["permission_code"]
    )

    op.create_table(
        "user_roles",
        Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
        Column("role_id", Integer, ForeignKey("roles.id"), primary_key=True),
        Column("created_at", DateTime, nullable=False),
        Column("created_by", Integer, ForeignKey("users.id"), nullable=True),
    )
    op.create_index("idx_user_roles_user", "user_roles", ["user_id"])
    op.create_index("idx_user_roles_role", "user_roles", ["role_id"])

    op.create_table(
        "user_permissions",
        Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
        Column(
            "permission_code",
            String(length=128),
            ForeignKey("permissions.code"),
            primary_key=True,
        ),
        Column("created_at", DateTime, nullable=False),
        Column("created_by", Integer, ForeignKey("users.id"), nullable=True),
    )
    op.create_index("idx_user_permissions_user", "user_permissions", ["user_id"])
    op.create_index(
        "idx_user_permissions_permission", "user_permissions", ["permission_code"]
    )

    # ---- Add roles.description, drop roles.permissions JSON ---------------
    with op.batch_alter_table("roles") as batch:
        batch.add_column(Column("description", String(length=1024), nullable=True))
        try:
            batch.drop_column("permissions")
        except Exception:
            # Already dropped on a manual fix-up — proceed.
            pass

    # ---- Migrate existing admin users into the admin role -----------------
    bind = op.get_bind()
    now = datetime.now(timezone.utc)

    admin_role_id_row = bind.execute(
        sa.text("SELECT id FROM roles WHERE name = 'admin'")
    ).fetchone()
    if admin_role_id_row is None:
        bind.execute(
            sa.text(
                "INSERT INTO roles (name, description, builtin, created_at, updated_at) "
                "VALUES ('admin', 'Built-in superadmin role.', :builtin, :now, :now)"
            ),
            {"builtin": True, "now": now},
        )
        admin_role_id = bind.execute(
            sa.text("SELECT id FROM roles WHERE name = 'admin'")
        ).fetchone()[0]
    else:
        admin_role_id = admin_role_id_row[0]

    # Backfill: every user.admin=True gets a user_roles row for the admin role.
    # ``users.admin`` may already be gone if this revision was re-run after a
    # manual fix-up; guard against that.
    user_table_cols = {
        r[0]
        for r in bind.execute(
            sa.text(
                "SELECT name FROM pragma_table_info('users')" if bind.dialect.name == "sqlite"
                else "SELECT column_name AS name FROM information_schema.columns "
                     "WHERE table_name='users'"
            )
        ).fetchall()
    } if bind.dialect.name in ("sqlite", "postgresql") else set()

    if "admin" in user_table_cols:
        admin_user_ids = [
            r[0]
            for r in bind.execute(
                sa.text("SELECT id FROM users WHERE admin = :true_val"),
                {"true_val": True if bind.dialect.name == "postgresql" else 1},
            ).fetchall()
        ]
        for uid in admin_user_ids:
            existing = bind.execute(
                sa.text(
                    "SELECT 1 FROM user_roles WHERE user_id = :u AND role_id = :r"
                ),
                {"u": uid, "r": admin_role_id},
            ).fetchone()
            if existing is None:
                bind.execute(
                    sa.text(
                        "INSERT INTO user_roles (user_id, role_id, created_at) "
                        "VALUES (:u, :r, :now)"
                    ),
                    {"u": uid, "r": admin_role_id, "now": now},
                )

        # ---- Drop users.admin ---------------------------------------------
        with op.batch_alter_table("users") as batch:
            batch.drop_column("admin")


def downgrade() -> None:
    # Restore the admin column with default false. Existing assignments to
    # the admin role do NOT auto-flip back to admin=True; ops would re-flag
    # via UPDATE if needed.
    with op.batch_alter_table("users") as batch:
        batch.add_column(
            Column("admin", Boolean, nullable=False, server_default=sa.false())
        )

    with op.batch_alter_table("roles") as batch:
        batch.add_column(Column("permissions", sa.JSON(), nullable=True))
        batch.drop_column("description")

    op.drop_index("idx_user_permissions_permission", table_name="user_permissions")
    op.drop_index("idx_user_permissions_user", table_name="user_permissions")
    op.drop_table("user_permissions")
    op.drop_index("idx_user_roles_role", table_name="user_roles")
    op.drop_index("idx_user_roles_user", table_name="user_roles")
    op.drop_table("user_roles")
    op.drop_index("idx_role_permissions_permission", table_name="role_permissions")
    op.drop_index("idx_role_permissions_role", table_name="role_permissions")
    op.drop_table("role_permissions")
    op.drop_table("permissions")

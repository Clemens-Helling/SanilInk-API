"""add_pending_invites

Revision ID: de9e2a3eda53
Revises: 8f4c2b1d7e90
Create Date: 2026-08-31 14:04:55.569700

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "de9e2a3eda53"
down_revision: Union[str, Sequence[str], None] = "8f4c2b1d7e90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Definieren des Enums mit den PostgreSQL-Dialekt-Tools
registration_status_enum = postgresql.ENUM(
    "INVITED",
    "AWAITING_KEY_GRANT",
    "ACTIVE",
    "EXPIRED",
    "REVOKED",
    name="registration_status",
)


def upgrade() -> None:
    """Upgrade schema."""
    # 1. ZUERST die Foreign Keys löschen, die auf die zu löschenden Tabellen verweisen
    # Mit if_exists=True ignoriert Alembic den Befehl sauber, falls der Constraint bereits gelöscht wurde:
    op.drop_constraint(
        op.f("protokolle_teacher_id_fkey"),
        "protokolle",
        type_="foreignkey",
        if_exists=True,
    )
    op.drop_constraint(
        op.f("protokolle_alert_id_fkey"),
        "protokolle",
        type_="foreignkey",
        if_exists=True,
    )

    # 2. JETZT können die Tabellen ohne Abhängigkeitsfehler gelöscht werden

    # 3. Neue Tabelle 'pending_registrations' erstellen
    op.create_table(
        "pending_registrations",
        sa.Column("registration_id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("invite_token_hash", sa.String(length=64), nullable=False),
        sa.Column("proposed_role", sa.String(length=255), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "INVITED",
                "AWAITING_KEY_GRANT",
                "ACTIVE",
                "EXPIRED",
                "REVOKED",
                name="registration_status",
            ),
            server_default="INVITED",
            nullable=False,
        ),
        sa.Column("invited_by", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("granted_by", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True
        ),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("registered_at", sa.DateTime(), nullable=True),
        sa.Column("granted_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "(status = 'ACTIVE' AND granted_by IS NOT NULL AND granted_at IS NOT NULL) OR (status != 'ACTIVE')",
            name="ck_active_requires_grant",
        ),
        sa.CheckConstraint(
            "(status = 'INVITED' AND user_id IS NULL) OR (status != 'INVITED')",
            name="ck_invited_has_no_user",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.customer_id"],
        ),
        sa.ForeignKeyConstraint(
            ["granted_by"],
            ["users.User_ID"],
        ),
        sa.ForeignKeyConstraint(
            ["invited_by"],
            ["users.User_ID"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.User_ID"],
        ),
        sa.PrimaryKeyConstraint("registration_id"),
        sa.UniqueConstraint("invite_token_hash"),
    )

    op.create_index(
        "ix_pending_registrations_awaiting_grant",
        "pending_registrations",
        ["customer_id", "status"],
        unique=False,
        postgresql_where=sa.text("status = 'AWAITING_KEY_GRANT'"),
    )
    op.create_index(
        "uq_pending_registrations_active_email",
        "pending_registrations",
        ["customer_id", "email"],
        unique=True,
        postgresql_where=sa.text("status IN ('INVITED', 'AWAITING_KEY_GRANT')"),
    )

    op.alter_column(
        "intake_keys",
        "encrypted_private_key",
        existing_type=sa.TEXT(),
        type_=sa.String(),
        existing_nullable=False,
    )
    op.alter_column("patient", "customer", existing_type=sa.INTEGER(), nullable=False)
    op.alter_column(
        "patient",
        "real_name",
        existing_type=sa.TEXT(),
        type_=sa.String(),
        existing_nullable=True,
    )
    op.alter_column(
        "patient",
        "real_last_name",
        existing_type=sa.TEXT(),
        type_=sa.String(),
        existing_nullable=True,
    )
    op.alter_column(
        "patient",
        "birth_day",
        existing_type=sa.TEXT(),
        type_=sa.String(),
        existing_nullable=True,
    )
    op.alter_column(
        "patient",
        "is_active",
        existing_type=sa.BOOLEAN(),
        nullable=True,
        existing_server_default=sa.text("true"),
    )
    op.alter_column(
        "pending_intakes",
        "sealed_payload",
        existing_type=sa.TEXT(),
        type_=sa.String(),
        existing_nullable=False,
    )
    op.alter_column(
        "protokolle", "customer", existing_type=sa.INTEGER(), nullable=False
    )
    op.alter_column(
        "protokolle",
        "measures",
        existing_type=sa.TEXT(),
        type_=sa.String(),
        existing_nullable=True,
    )
    op.drop_constraint(
        op.f("protokolle_teacher_id_fkey"),
        "protokolle",
        type_="foreignkey",
        if_exists=True,
    )
    op.drop_constraint(
        op.f("protokolle_alert_id_fkey"),
        "protokolle",
        type_="foreignkey",
        if_exists=True,
    )
    op.drop_column("protokolle", "teacher_id")
    op.alter_column(
        "user_keys",
        "is_active",
        existing_type=sa.BOOLEAN(),
        nullable=True,
        existing_server_default=sa.text("true"),
    )
    op.alter_column("users", "customer", existing_type=sa.INTEGER(), nullable=False)
    op.alter_column(
        "users",
        "is_active",
        existing_type=sa.BOOLEAN(),
        nullable=True,
        existing_server_default=sa.text("true"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "users",
        "is_active",
        existing_type=sa.BOOLEAN(),
        nullable=False,
        existing_server_default=sa.text("true"),
    )
    op.alter_column("users", "customer", existing_type=sa.INTEGER(), nullable=True)
    op.alter_column(
        "user_keys",
        "is_active",
        existing_type=sa.BOOLEAN(),
        nullable=False,
        existing_server_default=sa.text("true"),
    )
    op.add_column(
        "protokolle",
        sa.Column("teacher_id", sa.INTEGER(), autoincrement=False, nullable=True),
    )
    op.create_foreign_key(
        op.f("protokolle_alert_id_fkey"),
        "protokolle",
        "alarmierungen",
        ["alert_id"],
        ["alert_id"],
    )
    op.create_foreign_key(
        op.f("protokolle_teacher_id_fkey"),
        "protokolle",
        "teachers",
        ["teacher_id"],
        ["teacher_id"],
    )
    op.alter_column(
        "protokolle",
        "measures",
        existing_type=sa.String(),
        type_=sa.TEXT(),
        existing_nullable=True,
    )
    op.alter_column("protokolle", "customer", existing_type=sa.INTEGER(), nullable=True)
    op.alter_column(
        "pending_intakes",
        "sealed_payload",
        existing_type=sa.String(),
        type_=sa.TEXT(),
        existing_nullable=False,
    )
    op.alter_column(
        "patient",
        "is_active",
        existing_type=sa.BOOLEAN(),
        nullable=False,
        existing_server_default=sa.text("true"),
    )
    op.alter_column(
        "patient",
        "birth_day",
        existing_type=sa.String(),
        type_=sa.TEXT(),
        existing_nullable=True,
    )
    op.alter_column(
        "patient",
        "real_last_name",
        existing_type=sa.String(),
        type_=sa.TEXT(),
        existing_nullable=True,
    )
    op.alter_column(
        "patient",
        "real_name",
        existing_type=sa.String(),
        type_=sa.TEXT(),
        existing_nullable=True,
    )
    op.alter_column("patient", "customer", existing_type=sa.INTEGER(), nullable=True)
    op.alter_column(
        "intake_keys",
        "encrypted_private_key",
        existing_type=sa.String(),
        type_=sa.TEXT(),
        existing_nullable=False,
    )
    op.create_table(
        "locations",
        sa.Column("location_id", sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column("customer", sa.INTEGER(), autoincrement=False, nullable=True),
        sa.Column("name", sa.VARCHAR(length=255), autoincrement=False, nullable=True),
        sa.Column("symbol", sa.VARCHAR(length=10), autoincrement=False, nullable=True),
        sa.Column("is_active", sa.BOOLEAN(), autoincrement=False, nullable=True),
        sa.ForeignKeyConstraint(
            ["customer"],
            ["customers.customer_id"],
            name=op.f("locations_customer_fkey"),
        ),
        sa.PrimaryKeyConstraint("location_id", name=op.f("locations_pkey")),
    )
    op.create_table(
        "departements",
        sa.Column("department_id", sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column("customer", sa.INTEGER(), autoincrement=False, nullable=True),
        sa.Column(
            "departement_name",
            sa.VARCHAR(length=255),
            autoincrement=False,
            nullable=True,
        ),
        sa.Column("is_active", sa.BOOLEAN(), autoincrement=False, nullable=True),
        sa.Column("location", sa.INTEGER(), autoincrement=False, nullable=True),
        sa.ForeignKeyConstraint(
            ["customer"],
            ["customers.customer_id"],
            name=op.f("departements_customer_fkey"),
        ),
        sa.ForeignKeyConstraint(
            ["location"],
            ["locations.location_id"],
            name=op.f("departements_location_fkey"),
        ),
        sa.PrimaryKeyConstraint("department_id", name=op.f("departements_pkey")),
    )
    op.create_table(
        "teachers",
        sa.Column("teacher_id", sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column("customer", sa.INTEGER(), autoincrement=False, nullable=True),
        sa.Column(
            "first_name", sa.VARCHAR(length=255), autoincrement=False, nullable=True
        ),
        sa.Column(
            "last_name", sa.VARCHAR(length=255), autoincrement=False, nullable=True
        ),
        sa.Column("house", sa.VARCHAR(length=255), autoincrement=False, nullable=True),
        sa.ForeignKeyConstraint(
            ["customer"], ["customers.customer_id"], name=op.f("teachers_customer_fkey")
        ),
        sa.PrimaryKeyConstraint("teacher_id", name=op.f("teachers_pkey")),
    )
    op.create_table(
        "alarmierungen",
        sa.Column("alert_id", sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column("customer", sa.INTEGER(), autoincrement=False, nullable=True),
        sa.Column(
            "alert_received", postgresql.TIMESTAMP(), autoincrement=False, nullable=True
        ),
        sa.Column(
            "alert_type", sa.VARCHAR(length=255), autoincrement=False, nullable=True
        ),
        sa.Column(
            "symptom", sa.VARCHAR(length=255), autoincrement=False, nullable=True
        ),
        sa.ForeignKeyConstraint(
            ["customer"],
            ["customers.customer_id"],
            name=op.f("alarmierungen_customer_fkey"),
        ),
        sa.PrimaryKeyConstraint("alert_id", name=op.f("alarmierungen_pkey")),
    )
    op.drop_index(
        "uq_pending_registrations_active_email",
        table_name="pending_registrations",
        postgresql_where=sa.text("status IN ('INVITED', 'AWAITING_KEY_GRANT')"),
    )
    op.drop_index(
        "ix_pending_registrations_awaiting_grant",
        table_name="pending_registrations",
        postgresql_where=sa.text("status = 'AWAITING_KEY_GRANT'"),
    )
    op.drop_table("pending_registrations")

    # Lösche den Enum-Typ beim Downgrade
    registration_status_enum.drop(op.get_bind(), checkfirst=True)

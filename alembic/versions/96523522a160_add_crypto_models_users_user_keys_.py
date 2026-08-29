"""Bootstrap legacy schema with crypto additions

Revision ID: 96523522a160
Revises:
Create Date: 2026-08-09 02:10:46.974225
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "96523522a160"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("customer_id", sa.Integer(), primary_key=True),
        sa.Column("customer_number", sa.String(length=100), nullable=False, unique=True),
        sa.Column("contact_person_first_name", sa.String(length=255)),
        sa.Column("contact_person_last_name", sa.String(length=255)),
        sa.Column("email", sa.String(length=100)),
        sa.Column("phone_number", sa.String(length=100)),
    )

    op.create_table(
        "users",
        sa.Column("User_ID", sa.Integer(), primary_key=True),
        sa.Column("customer", sa.Integer(), sa.ForeignKey("customers.customer_id")),
        sa.Column("name", sa.String(length=255)),
        sa.Column("last_name", sa.String(length=255)),
        sa.Column("teacher", sa.Integer()),
        sa.Column("departement", sa.Integer()),
        sa.Column("karten_nummer", sa.String(length=255)),
        sa.Column("permission", sa.String(length=255)),
        sa.Column("username", sa.String(length=255)),
        sa.Column("email", sa.String(length=255)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    op.create_table(
        "teachers",
        sa.Column("teacher_id", sa.Integer(), primary_key=True),
        sa.Column("customer", sa.Integer(), sa.ForeignKey("customers.customer_id")),
        sa.Column("first_name", sa.String(length=255)),
        sa.Column("last_name", sa.String(length=255)),
        sa.Column("house", sa.String(length=255)),
    )

    op.create_table(
        "locations",
        sa.Column("location_id", sa.Integer(), primary_key=True),
        sa.Column("customer", sa.Integer(), sa.ForeignKey("customers.customer_id")),
        sa.Column("name", sa.String(length=255)),
        sa.Column("symbol", sa.String(length=10)),
        sa.Column("is_active", sa.Boolean()),
    )

    op.create_table(
        "departements",
        sa.Column("department_id", sa.Integer(), primary_key=True),
        sa.Column("customer", sa.Integer(), sa.ForeignKey("customers.customer_id")),
        sa.Column("departement_name", sa.String(length=255)),
        sa.Column("is_active", sa.Boolean()),
        sa.Column("location", sa.Integer(), sa.ForeignKey("locations.location_id")),
    )

    op.create_table(
        "alarmierungen",
        sa.Column("alert_id", sa.Integer(), primary_key=True),
        sa.Column("customer", sa.Integer(), sa.ForeignKey("customers.customer_id")),
        sa.Column("alert_received", sa.DateTime()),
        sa.Column("alert_type", sa.String(length=255)),
        sa.Column("symptom", sa.String(length=255)),
    )

    op.create_table(
        "patient",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("customer", sa.Integer(), sa.ForeignKey("customers.customer_id")),
        sa.Column("real_name", sa.Text()),
        sa.Column("real_last_name", sa.Text()),
        sa.Column("birth_day", sa.Text()),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("pseudonym", sa.String(length=255), unique=True),
        sa.Column("encrypted_real_name", sa.String()),
        sa.Column("encrypted_real_last_name", sa.String()),
        sa.Column("encrypted_birth_day", sa.String()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )

    op.create_table(
        "protokolle",
        sa.Column("protokoll_id", sa.Integer(), primary_key=True),
        sa.Column("customer", sa.Integer(), sa.ForeignKey("customers.customer_id")),
        sa.Column("alert_id", sa.Integer(), sa.ForeignKey("alarmierungen.alert_id")),
        sa.Column("pseudonym", sa.String(length=255), sa.ForeignKey("patient.pseudonym")),
        sa.Column("teacher_id", sa.Integer(), sa.ForeignKey("teachers.teacher_id")),
        sa.Column("operation_end", sa.DateTime()),
        sa.Column("status", sa.String(length=255)),
        sa.Column("pulse", sa.Integer()),
        sa.Column("spo2", sa.Integer()),
        sa.Column("blood_pressure", sa.String(length=255)),
        sa.Column("temperature", sa.Integer()),
        sa.Column("blood_sugar", sa.Integer()),
        sa.Column("pain", sa.String(length=255)),
        sa.Column("measures", sa.Text()),
        sa.Column("abhol_massnahme", sa.String(length=255)),
        sa.Column("parents_notified_by", sa.String(length=255)),
        sa.Column("parents_notified_at", sa.DateTime()),
        sa.Column("hospital", sa.String(length=255)),
        sa.Column("medic_id", sa.Integer()),
    )

    op.create_table(
        "user_keys",
        sa.Column("key_id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.User_ID"), nullable=False),
        sa.Column("public_key", sa.String(), nullable=False),
        sa.Column("encrypted_private_key", sa.String(), nullable=False),
        sa.Column("argon2_salt", sa.String(length=255), nullable=False),
        sa.Column("argon2_time_cost_a", sa.Integer()),
        sa.Column("argon2_memory_cost_a", sa.Integer()),
        sa.Column("argon2_parallelism_a", sa.Integer()),
        sa.Column("stored_key", sa.String(length=255), nullable=False),
        sa.Column("argon2_salt_b", sa.String(length=255), nullable=False),
        sa.Column("argon2_time_cost_b", sa.Integer(), nullable=False),
        sa.Column("argon2_memory_cost_b", sa.Integer(), nullable=False),
        sa.Column("argon2_parallelism_b", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )

    op.create_table(
        "customer_key_slots",
        sa.Column("slot_id", sa.Integer(), primary_key=True),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.customer_id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.User_ID"), nullable=False),
        sa.Column("ephemeral_public_key", sa.String(length=255), nullable=False),
        sa.Column("encrypted_gek", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.execute("ALTER TABLE patient ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_policies
                WHERE schemaname = current_schema()
                  AND tablename = 'patient'
                  AND policyname = 'patient_tenant_isolation'
            ) THEN
                CREATE POLICY patient_tenant_isolation ON patient
                    FOR ALL USING (customer = current_setting('app.current_customer_id')::INTEGER);
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS patient_tenant_isolation ON patient")
    op.execute("ALTER TABLE patient DISABLE ROW LEVEL SECURITY")

    op.drop_table("customer_key_slots")
    op.drop_table("user_keys")
    op.drop_table("protokolle")
    op.drop_table("patient")
    op.drop_table("alarmierungen")
    op.drop_table("departements")
    op.drop_table("locations")
    op.drop_table("teachers")
    op.drop_table("users")
    op.drop_table("customers")

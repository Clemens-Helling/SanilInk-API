"""Add tenant isolation policies for PostgreSQL RLS.

Revision ID: 8f4c2b1d7e90
Revises: 96523522a160
"""

from typing import Sequence, Union

from alembic import op


revision: str = "8f4c2b1d7e90"
down_revision: Union[str, Sequence[str], None] = "96523522a160"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TENANT_COLUMNS = {
    "users": "customer",
    "teachers": "customer",
    "locations": "customer",
    "departements": "customer",
    "alarmierungen": "customer",
    "patient": "customer",
    "protokolle": "customer",
    "sani_protokoll": "customer",
    "materials": "customer",
    "protokoll_materials": "customer",
    "customer_key_slots": "customer_id",
    "intake_keys": "customer_id",
    "pending_intakes": "customer_id",
}


def upgrade() -> None:
    for table, column in TENANT_COLUMNS.items():
        policy_name = f"{table}_tenant_isolation"
        op.execute(
            f"""DO $$
                BEGIN
                    IF to_regclass(current_schema() || '.{table}') IS NOT NULL THEN
                        EXECUTE 'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY';
                        EXECUTE 'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY';
                        EXECUTE 'DROP POLICY IF EXISTS "{policy_name}" ON "{table}"';
                        EXECUTE 'CREATE POLICY "{policy_name}" ON "{table}"
                            FOR ALL
                            USING ("{column}" = current_setting(''app.current_customer_id'', true)::integer)
                            WITH CHECK ("{column}" = current_setting(''app.current_customer_id'', true)::integer)';
                    END IF;
                END $$;"""
        )

    op.execute("ALTER TABLE user_keys ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE user_keys FORCE ROW LEVEL SECURITY")
    op.execute(
        """CREATE POLICY user_keys_tenant_isolation ON user_keys
        FOR ALL
        USING (EXISTS (
            SELECT 1 FROM users
            WHERE users."User_ID" = user_keys.user_id
              AND users.customer = current_setting('app.current_customer_id', true)::integer
        ))
        WITH CHECK (EXISTS (
            SELECT 1 FROM users
            WHERE users."User_ID" = user_keys.user_id
              AND users.customer = current_setting('app.current_customer_id', true)::integer
        ))"""
    )

    op.execute(
        'CREATE TABLE IF NOT EXISTS intake_keys (\n    intake_key_id INTEGER PRIMARY KEY,\n    customer_id INTEGER NOT NULL REFERENCES customers(customer_id),\n    label VARCHAR(255) NOT NULL,\n    public_key VARCHAR(255) NOT NULL,\n    encrypted_private_key TEXT NOT NULL,\n    created_by INTEGER NOT NULL REFERENCES users("User_ID"),\n    revoked_at TIMESTAMP NULL,\n    created_at TIMESTAMP DEFAULT NOW()\n)'
    )
    op.execute(
        "CREATE TABLE IF NOT EXISTS pending_intakes (\n    pending_intake_id INTEGER PRIMARY KEY,\n    customer_id INTEGER NOT NULL REFERENCES customers(customer_id),\n    intake_key_id INTEGER NOT NULL REFERENCES intake_keys(intake_key_id),\n    sealed_payload TEXT NOT NULL,\n    status VARCHAR(32) NOT NULL DEFAULT 'pending',\n    claimed_by INTEGER REFERENCES users(\"User_ID\"),\n    resulting_patient_id INTEGER REFERENCES patient(id),\n    created_at TIMESTAMP DEFAULT NOW(),\n    updated_at TIMESTAMP DEFAULT NOW()\n)"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS user_keys_tenant_isolation ON user_keys")
    op.execute("ALTER TABLE user_keys DISABLE ROW LEVEL SECURITY")
    op.execute("DROP TABLE IF EXISTS pending_intakes")
    op.execute("DROP TABLE IF EXISTS intake_keys")

    for table in reversed(tuple(TENANT_COLUMNS)):
        op.execute(
            f"""DO $$
            BEGIN
                IF to_regclass(current_schema() || '.{table}') IS NOT NULL THEN
                    EXECUTE 'DROP POLICY IF EXISTS "{table}_tenant_isolation" ON "{table}"';
                    EXECUTE 'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY';
                END IF;
            END $$;"""
        )

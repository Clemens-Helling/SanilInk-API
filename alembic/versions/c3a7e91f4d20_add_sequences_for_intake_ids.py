"""add sequences for manually created intake tables

Revision ID: c3a7e91f4d20
Revises: 42696f3ea5b8
"""

from typing import Sequence, Union

from alembic import op


revision: str = "c3a7e91f4d20"
down_revision: Union[str, Sequence[str], None] = "42696f3ea5b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Give the primary keys of the manually created tables PostgreSQL sequences."""
    for table_name, column_name in (
        ("intake_keys", "intake_key_id"),
        ("pending_intakes", "pending_intake_id"),
    ):
        op.execute(
            f"""
            DO $$
            DECLARE
                sequence_name text;
                maximum_id bigint;
            BEGIN
                sequence_name := pg_get_serial_sequence(
                    format('%I.%I', current_schema(), '{table_name}'),
                    '{column_name}'
                );

                IF sequence_name IS NULL THEN
                    sequence_name := format(
                        '%I.%I',
                        current_schema(),
                        '{table_name}_{column_name}_seq'
                    );
                    EXECUTE format('CREATE SEQUENCE IF NOT EXISTS %s', sequence_name);
                    EXECUTE format(
                        'ALTER SEQUENCE %s OWNED BY %I.%I.%I',
                        sequence_name,
                        current_schema(),
                        '{table_name}',
                        '{column_name}'
                    );
                    EXECUTE format(
                        'ALTER TABLE %I.%I ALTER COLUMN %I SET DEFAULT nextval(%L::regclass)',
                        current_schema(),
                        '{table_name}',
                        '{column_name}',
                        sequence_name
                    );
                END IF;

                EXECUTE format(
                    'SELECT MAX(%I) FROM %I.%I',
                    '{column_name}',
                    current_schema(),
                    '{table_name}'
                ) INTO maximum_id;

                PERFORM setval(
                    sequence_name::regclass,
                    COALESCE(maximum_id, 1),
                    maximum_id IS NOT NULL
                );
            END $$;
            """
        )


def downgrade() -> None:
    """Keep the sequences in place because the intake tables depend on generated IDs."""

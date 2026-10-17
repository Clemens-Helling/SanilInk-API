"""add encrypted intake details to patients

Revision ID: da815f20bc31
Revises: c3a7e91f4d20
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "da815f20bc31"
down_revision: Union[str, Sequence[str], None] = "c3a7e91f4d20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "patient",
        sa.Column("encrypted_intake_description", sa.String(), nullable=True),
    )
    op.add_column(
        "patient",
        sa.Column("encrypted_initial_measures", sa.String(), nullable=True),
    )
    op.add_column(
        "patient",
        sa.Column("encrypted_witnesses", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("patient", "encrypted_witnesses")
    op.drop_column("patient", "encrypted_initial_measures")
    op.drop_column("patient", "encrypted_intake_description")

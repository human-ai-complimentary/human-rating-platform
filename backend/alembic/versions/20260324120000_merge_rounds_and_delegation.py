"""merge rounds and delegation heads

Revision ID: 20260324120000
Revises: 20260312084500, 20260309000000
Create Date: 2026-03-24 12:00:00.000000
"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "20260324120000"
down_revision: Union[str, Sequence[str], None] = ("20260312084500", "20260309000000")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

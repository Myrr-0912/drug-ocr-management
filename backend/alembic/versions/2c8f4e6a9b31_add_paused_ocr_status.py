"""add_paused_ocr_status

Revision ID: 2c8f4e6a9b31
Revises: 7f3b9c2a4d10
Create Date: 2026-05-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "2c8f4e6a9b31"
down_revision: Union[str, None] = "7f3b9c2a4d10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_OLD_VALUES = "'pending','success','failed','confirmed'"
_NEW_VALUES = "'pending','success','failed','confirmed','paused'"


def upgrade() -> None:
    op.execute(
        f"ALTER TABLE ocr_records MODIFY status ENUM({_NEW_VALUES}) NOT NULL"
    )
    op.execute(
        f"ALTER TABLE ocr_record_images MODIFY status ENUM({_NEW_VALUES}) NOT NULL"
    )


def downgrade() -> None:
    op.execute("UPDATE ocr_records SET status = 'pending' WHERE status = 'paused'")
    op.execute("UPDATE ocr_record_images SET status = 'pending' WHERE status = 'paused'")
    op.execute(
        f"ALTER TABLE ocr_record_images MODIFY status ENUM({_OLD_VALUES}) NOT NULL"
    )
    op.execute(
        f"ALTER TABLE ocr_records MODIFY status ENUM({_OLD_VALUES}) NOT NULL"
    )

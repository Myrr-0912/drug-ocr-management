"""add_ocr_record_images

Revision ID: 7f3b9c2a4d10
Revises: 389e8ca13cec
Create Date: 2026-05-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7f3b9c2a4d10'
down_revision: Union[str, None] = '389e8ca13cec'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'ocr_record_images',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('ocr_record_id', sa.Integer(), nullable=False, comment='所属 OCR 主记录'),
        sa.Column('image_path', sa.String(length=500), nullable=False, comment='上传图片路径'),
        sa.Column('image_index', sa.Integer(), nullable=False, comment='上传顺序，从 1 开始'),
        sa.Column('raw_text', sa.Text(), nullable=True, comment='单图 OCR 原始识别文本'),
        sa.Column('extracted_data', sa.JSON(), nullable=True, comment='单图结构化提取结果'),
        sa.Column('confidence', sa.Float(), nullable=True, comment='单图字段完整度 0~1'),
        sa.Column('status', sa.Enum('pending', 'success', 'failed', 'confirmed', name='ocrstatus'), nullable=False),
        sa.Column('error_message', sa.String(length=500), nullable=True, comment='单图错误信息'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['ocr_record_id'], ['ocr_records.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_ocr_record_images_ocr_record_id'), 'ocr_record_images', ['ocr_record_id'], unique=False)
    op.create_index(op.f('ix_ocr_record_images_status'), 'ocr_record_images', ['status'], unique=False)
    op.create_index(
        'ix_ocr_record_images_record_index',
        'ocr_record_images',
        ['ocr_record_id', 'image_index'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_ocr_record_images_record_index', table_name='ocr_record_images')
    op.drop_index(op.f('ix_ocr_record_images_status'), table_name='ocr_record_images')
    op.drop_index(op.f('ix_ocr_record_images_ocr_record_id'), table_name='ocr_record_images')
    op.drop_table('ocr_record_images')

"""init_all_tables

Revision ID: 0336870d7cc1
Revises: 
Create Date: 2026-04-12 04:41:02.440171

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0336870d7cc1'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 建表顺序：手动处理 drug_batches <-> ocr_records 循环外键
    # 策略：先建两表（暂不加对方的 FK），最后用 create_foreign_key 补加

    # 1. users
    op.create_table('users',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('username', sa.String(length=50), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('real_name', sa.String(length=50), nullable=True),
    sa.Column('role', sa.Enum('admin', 'pharmacist', 'user', name='userrole'), nullable=False),
    sa.Column('phone', sa.String(length=20), nullable=True),
    sa.Column('email', sa.String(length=100), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)

    # 2. drugs (依赖 users)
    op.create_table('drugs',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False, comment='药品名称'),
    sa.Column('common_name', sa.String(length=200), nullable=True, comment='通用名'),
    sa.Column('approval_number', sa.String(length=100), nullable=True, comment='批准文号'),
    sa.Column('specification', sa.String(length=100), nullable=True, comment='规格'),
    sa.Column('dosage_form', sa.String(length=50), nullable=True, comment='剂型'),
    sa.Column('manufacturer', sa.String(length=200), nullable=True, comment='生产企业'),
    sa.Column('category', sa.String(length=50), nullable=True, comment='分类'),
    sa.Column('storage_condition', sa.String(length=200), nullable=True, comment='储存条件'),
    sa.Column('description', sa.Text(), nullable=True, comment='备注说明'),
    sa.Column('image_url', sa.String(length=500), nullable=True, comment='药品图片路径'),
    sa.Column('created_by', sa.Integer(), nullable=True, comment='创建人'),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_drugs_approval_number'), 'drugs', ['approval_number'], unique=True)
    op.create_index(op.f('ix_drugs_manufacturer'), 'drugs', ['manufacturer'], unique=False)
    op.create_index(op.f('ix_drugs_name'), 'drugs', ['name'], unique=False)

    # 3. ocr_records (依赖 drugs/users，暂不加 batch_id FK 以打破循环)
    op.create_table('ocr_records',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('image_path', sa.String(length=500), nullable=False, comment='上传图片路径'),
    sa.Column('raw_text', sa.Text(), nullable=True, comment='OCR 原始识别文本'),
    sa.Column('extracted_data', sa.JSON(), nullable=True, comment='结构化提取结果'),
    sa.Column('confidence', sa.Float(), nullable=True, comment='识别置信度 0~1'),
    sa.Column('status', sa.Enum('pending', 'success', 'failed', 'confirmed', name='ocrstatus'), nullable=False),
    sa.Column('drug_id', sa.Integer(), nullable=True),
    sa.Column('batch_id', sa.Integer(), nullable=True),  # FK 在 drug_batches 建完后追加
    sa.Column('operator_id', sa.Integer(), nullable=True),
    sa.Column('error_message', sa.String(length=500), nullable=True, comment='错误信息'),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['drug_id'], ['drugs.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['operator_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ocr_records_drug_id'), 'ocr_records', ['drug_id'], unique=False)
    op.create_index(op.f('ix_ocr_records_status'), 'ocr_records', ['status'], unique=False)

    # 4. drug_batches (依赖 drugs/ocr_records，source_ocr_id FK 在 ocr_records 已存在后追加)
    op.create_table('drug_batches',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('drug_id', sa.Integer(), nullable=False),
    sa.Column('batch_number', sa.String(length=100), nullable=False, comment='批号'),
    sa.Column('production_date', sa.Date(), nullable=True, comment='生产日期'),
    sa.Column('expiry_date', sa.Date(), nullable=False, comment='有效期至'),
    sa.Column('quantity', sa.Integer(), nullable=False, comment='当前库存量'),
    sa.Column('unit', sa.String(length=20), nullable=False, comment='单位'),
    sa.Column('status', sa.Enum('normal', 'near_expiry', 'expired', name='batchstatus'), nullable=False, comment='状态'),
    sa.Column('source_ocr_id', sa.Integer(), nullable=True, comment='来源 OCR 记录'),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['drug_id'], ['drugs.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['source_ocr_id'], ['ocr_records.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    mysql_charset='utf8mb4',
    mysql_engine='InnoDB'
    )
    op.create_index(op.f('ix_drug_batches_batch_number'), 'drug_batches', ['batch_number'], unique=False)
    op.create_index(op.f('ix_drug_batches_drug_id'), 'drug_batches', ['drug_id'], unique=False)
    op.create_index(op.f('ix_drug_batches_expiry_date'), 'drug_batches', ['expiry_date'], unique=False)

    # 5. 补加 ocr_records.batch_id -> drug_batches 的外键
    op.create_foreign_key(
        'fk_ocr_records_batch_id', 'ocr_records', 'drug_batches',
        ['batch_id'], ['id'], ondelete='SET NULL'
    )

    # 6. alerts (依赖 drugs/drug_batches/users)
    op.create_table('alerts',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('alert_type', sa.Enum('expiry_warning', 'expired', 'low_stock', name='alerttype'), nullable=False),
    sa.Column('drug_id', sa.Integer(), nullable=True),
    sa.Column('batch_id', sa.Integer(), nullable=True),
    sa.Column('message', sa.String(length=500), nullable=False),
    sa.Column('severity', sa.Enum('info', 'warning', 'critical', name='alertseverity'), nullable=False),
    sa.Column('is_read', sa.Boolean(), nullable=False),
    sa.Column('is_resolved', sa.Boolean(), nullable=False),
    sa.Column('resolved_by', sa.Integer(), nullable=True),
    sa.Column('resolved_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['batch_id'], ['drug_batches.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['drug_id'], ['drugs.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['resolved_by'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_alerts_alert_type'), 'alerts', ['alert_type'], unique=False)
    op.create_index(op.f('ix_alerts_drug_id'), 'alerts', ['drug_id'], unique=False)
    op.create_index(op.f('ix_alerts_is_read'), 'alerts', ['is_read'], unique=False)

    # 7. inventory_records (依赖 drugs/drug_batches/users)
    op.create_table('inventory_records',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('drug_id', sa.Integer(), nullable=False),
    sa.Column('batch_id', sa.Integer(), nullable=False),
    sa.Column('operation_type', sa.Enum('in', 'out', 'adjust', name='operationtype'), nullable=False, comment='操作类型'),
    sa.Column('quantity', sa.Integer(), nullable=False, comment='数量'),
    sa.Column('operator_id', sa.Integer(), nullable=True, comment='操作人'),
    sa.Column('remark', sa.String(length=500), nullable=True, comment='备注'),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['batch_id'], ['drug_batches.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['drug_id'], ['drugs.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['operator_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_inventory_records_batch_id'), 'inventory_records', ['batch_id'], unique=False)
    op.create_index(op.f('ix_inventory_records_drug_id'), 'inventory_records', ['drug_id'], unique=False)


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_inventory_records_drug_id'), table_name='inventory_records')
    op.drop_index(op.f('ix_inventory_records_batch_id'), table_name='inventory_records')
    op.drop_table('inventory_records')
    op.drop_index(op.f('ix_alerts_is_read'), table_name='alerts')
    op.drop_index(op.f('ix_alerts_drug_id'), table_name='alerts')
    op.drop_index(op.f('ix_alerts_alert_type'), table_name='alerts')
    op.drop_table('alerts')
    op.drop_index(op.f('ix_drugs_name'), table_name='drugs')
    op.drop_index(op.f('ix_drugs_manufacturer'), table_name='drugs')
    op.drop_index(op.f('ix_drugs_approval_number'), table_name='drugs')
    op.drop_table('drugs')
    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_table('users')
    op.drop_index(op.f('ix_ocr_records_status'), table_name='ocr_records')
    op.drop_index(op.f('ix_ocr_records_drug_id'), table_name='ocr_records')
    op.drop_table('ocr_records')
    op.drop_index(op.f('ix_drug_batches_expiry_date'), table_name='drug_batches')
    op.drop_index(op.f('ix_drug_batches_drug_id'), table_name='drug_batches')
    op.drop_index(op.f('ix_drug_batches_batch_number'), table_name='drug_batches')
    op.drop_table('drug_batches')
    # ### end Alembic commands ###

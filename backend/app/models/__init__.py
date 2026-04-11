# 导入所有模型，确保 Alembic 自动迁移能发现全部表
from app.models.user import User, UserRole  # noqa
from app.models.drug import Drug  # noqa
from app.models.batch import DrugBatch, BatchStatus  # noqa
from app.models.inventory import InventoryRecord, OperationType  # noqa
from app.models.ocr_record import OcrRecord, OcrStatus  # noqa
from app.models.alert import Alert, AlertType, AlertSeverity  # noqa
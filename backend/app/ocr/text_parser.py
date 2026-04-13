"""
药品信息文本解析器
从 OCR 原始文本中用正则 + 关键词提取结构化药品字段
"""
import re
from datetime import date

from app.schemas.ocr import ExtractedDrugData


# -------- 正则模式 --------

# 批准文号：国药准字 H/Z/S/J/B + 8位数字
_RE_APPROVAL = re.compile(r"国药准字[HhZzSsJjBb]\d{8}")

# 批号：通常为6~12位数字/字母，紧跟"批号"或"批次"关键词
_RE_BATCH = re.compile(
    r"(?:批号|批次号|Lot\.?No\.?)[：:.\s]*([A-Za-z0-9]{4,20})"
)

# 生产日期（多种格式）
_RE_PROD_DATE = re.compile(
    r"(?:生产日期|制造日期|生产年月)[：:.\s]*"
    r"(\d{4}[-./年]\d{1,2}[-./月]?\d{0,2}日?)"
)

# 有效期（多种格式）
_RE_EXPIRY = re.compile(
    r"(?:有效期(?:至)?|失效日期|效期至)[：:.\s]*"
    r"(\d{4}[-./年]\d{1,2}[-./月]?\d{0,2}日?)"
)

# 规格：数字 + 单位 + × + 数字 + 粒/片/支/袋/瓶/mL/mg/g
_RE_SPEC = re.compile(
    r"规格[：:.\s]*([0-9.]+\s*(?:mg|g|mL|μg|IU|万IU)\s*[×x]\s*\d+\s*(?:粒|片|支|袋|瓶|粒/瓶|片/盒|支/盒)?)"
)

# 生产企业
_RE_MANUFACTURER = re.compile(
    r"(?:生产企业|生产厂家|厂家|制造商)[：:.\s]*([^\n]{4,40}(?:公司|厂|集团))"
)

# 数量（整件/盒）
_RE_QUANTITY = re.compile(r"(\d+)\s*(?:盒|瓶|袋|件|支|粒)")


def _normalize_date_str(raw: str) -> str | None:
    """将各种日期格式统一为 YYYY-MM-DD 字符串，无法解析则返回 None"""
    if not raw:
        return None
    raw = raw.strip()
    # 替换中文单位为分隔符
    cleaned = re.sub(r"[年月]", "-", raw).replace("日", "").strip("-")
    # 处理 YYYYMM 六位数字
    if re.fullmatch(r"\d{6}", cleaned):
        return f"{cleaned[:4]}-{cleaned[4:6]}-01"
    # 标准 YYYY-M-D 或 YYYY-MM
    parts = re.split(r"[-./]", cleaned)
    if len(parts) >= 2:
        year = parts[0].zfill(4)
        month = parts[1].zfill(2)
        day = parts[2].zfill(2) if len(parts) > 2 and parts[2] else "01"
        try:
            # 简单校验范围
            y, m, d = int(year), int(month), int(day)
            if 2000 <= y <= 2100 and 1 <= m <= 12 and 1 <= d <= 31:
                return f"{year}-{month}-{day}"
        except ValueError:
            pass
    return None


def parse_drug_info(raw_text: str) -> ExtractedDrugData:
    """
    从 OCR 原始文本提取结构化药品信息。
    每个字段用正则匹配，未命中则为 None。
    """
    text = raw_text or ""

    # 批准文号
    approval = None
    m = _RE_APPROVAL.search(text)
    if m:
        approval = m.group(0)

    # 药品名称：取第一行非空内容作为候选名称，常见格式为第一行就是药品名
    name = None
    for line in text.splitlines():
        line = line.strip()
        # 跳过明显是字段行（含冒号）或过短的行
        if line and len(line) >= 3 and "：" not in line and ":" not in line:
            # 排除全数字行、URL 行
            if not re.fullmatch(r"[\d\s\-/]+", line):
                name = line
                break

    # 批号
    batch_number = None
    m = _RE_BATCH.search(text)
    if m:
        batch_number = m.group(1)

    # 生产日期
    production_date = None
    m = _RE_PROD_DATE.search(text)
    if m:
        production_date = _normalize_date_str(m.group(1))

    # 有效期
    expiry_date = None
    m = _RE_EXPIRY.search(text)
    if m:
        expiry_date = _normalize_date_str(m.group(1))

    # 规格
    specification = None
    m = _RE_SPEC.search(text)
    if m:
        specification = m.group(1).strip()

    # 生产企业
    manufacturer = None
    m = _RE_MANUFACTURER.search(text)
    if m:
        manufacturer = m.group(1).strip()

    # 数量（取第一个匹配值）
    quantity = None
    m = _RE_QUANTITY.search(text)
    if m:
        quantity = int(m.group(1))

    return ExtractedDrugData(
        name=name,
        approval_number=approval,
        manufacturer=manufacturer,
        specification=specification,
        batch_number=batch_number,
        production_date=production_date,
        expiry_date=expiry_date,
        quantity=quantity,
    )

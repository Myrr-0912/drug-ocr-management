"""
药品信息文本解析器 — 多级兜底策略 Pipeline

执行层级：
  Tier 1 — 增强型正则提取（中文关键词间加 \\s* 兼容排版空格）
  Tier 2 — difflib 模糊匹配兜底（正则失败时启动，相似度阈值 > 0.8）
  Tier 3 — DeepSeek LLM 兜底（核心字段均为空时触发，读取 DEEPSEEK_API_KEY）

对外接口保持不变：parse_drug_info(raw_text: str) -> ExtractedDrugData
"""
import re
import json
import os
import difflib
import logging
from typing import Optional

import httpx

from app.schemas.ocr import ExtractedDrugData

logger = logging.getLogger(__name__)


# ============================================================
# Tier 1 — 增强型正则模式
# 所有中文关键词字符间均加入 \\s*，兼容 OCR 识别出的排版空格
# 例如：有 效 期 / 批  号 / 国 药 准 字
# ============================================================

# 批准文号：字母+8位数字，字符间及数字间均允许空格（如：H 1 2 3 4 5 6 7 8）
_RE_APPROVAL = re.compile(r"国\s*药\s*准\s*字\s*[HhZzSsJjBb](?:\s*\d){8}")

# 药品名称：优先匹配"通用名称"/"药品名称"关键词后的值
_RE_DRUG_NAME = re.compile(
    r"(?:通\s*用\s*名\s*称?|药\s*品\s*名\s*称)[：:.\s]*([^\n（(【\[\]]{2,20})"
)

# 批号：支持多种写法及【产品批号】\n值格式
_RE_BATCH = re.compile(
    r"(?:产\s*品\s*批\s*号|批\s*号|批\s*次\s*号|Lot\.?No\.?)[】：:.\s]*([A-Za-z0-9\-]{4,20})"
)

# 生产日期：支持【生产日期】\n值格式（】作为分隔符）
_RE_PROD_DATE = re.compile(
    r"(?:生\s*产\s*日\s*期|制\s*造\s*日\s*期|生\s*产\s*年\s*月)[】：:.\s]*"
    r"(\d{4}[-./年]\d{1,2}[-./月]?\d{0,2}日?)"
)

# 有效期（正向）：支持"有效期至"及"有 效 期"排版空格格式
_RE_EXPIRY = re.compile(
    r"(?:有\s*效\s*期(?:至)?|失\s*效\s*日\s*期|效\s*期\s*至)[】至：:.\s]*"
    r"(\d{4}[-./年]\d{1,2}[-./月]?\d{0,2}日?)"
)

# 有效期（反向）：OCR 读取贴纸时日期出现在关键词之前
_RE_EXPIRY_BEFORE = re.compile(
    r"(\d{4}[-./年]\d{1,2}[-./月]?\d{0,2}日?)\s*\n+\s*(?:【)?有\s*效\s*期"
)

# 规格：兼容"规  格"内部多余空格
_RE_SPEC = re.compile(
    r"规\s*格[】：:.\s]*([^\n【】\[\]（）]{2,50})"
)

# 生产企业：关键词后必须紧跟冒号，防止在适应症描述中误匹配
_RE_MANUFACTURER = re.compile(
    r"(?:生\s*产\s*企\s*业|企\s*业\s*名\s*称|生\s*产\s*厂\s*家|制\s*造\s*商)[：:]\s*"
    r"([^【】\n：:（）]{2,30}(?:公司|厂|集团))"
)

# 药品名称后缀：通过剂型后缀定位药品名（作为关键词匹配的兜底）
_RE_DRUG_SUFFIX = re.compile(
    r"^([^\n【】（）：:\d]{2,15}"
    r"(?:膏|片|胶囊|颗粒|丸|液|散|贴膏|注射液|乳膏|软膏|栓|糖浆|滴眼液|口服液))"
)

# 数量：支持常见药品单位
_RE_QUANTITY = re.compile(r"(\d+)\s*(?:盒|瓶|袋|件|支|粒|贴)")

# Tier 2 辅助：从行中提取日期值
_RE_DATE_VALUE = re.compile(r"\d{4}[-./年]\d{1,2}[-./月]?\d{0,2}日?")
# Tier 2 辅助：从行中提取批号值（字母数字组合）
_RE_BATCH_VALUE = re.compile(r"[A-Za-z0-9\-]{4,20}")


# ============================================================
# Tier 2 — 模糊匹配关键词表
# key 对应字段名，value 为该字段所有可能的关键词变体
# ============================================================

_FUZZY_KEYWORDS: dict[str, list[str]] = {
    "batch_number":    ["批号", "产品批号", "批次号", "LotNo"],
    "expiry_date":     ["有效期至", "有效期", "失效日期", "效期至"],
    "production_date": ["生产日期", "制造日期", "生产年月"],
    "manufacturer":    ["生产企业", "企业名称", "生产厂家", "制造商"],
    "specification":   ["规格"],
    "approval_number": ["国药准字"],
    "name":            ["通用名称", "药品名称"],
}


# ============================================================
# Tier 3 — LLM 提取接口（当前为 Stub，未激活）
# ============================================================

# LLM 系统提示词：指导模型输出标准 JSON
_LLM_SYSTEM_PROMPT = """你是一个专业的药品信息结构化提取助手。
请从用户提供的药盒 OCR 原始文本中，严格按照以下 JSON 格式提取信息：
{
  "name": "药品通用名称（字符串或 null）",
  "approval_number": "批准文号，格式为国药准字+字母+8位数字（字符串或 null）",
  "manufacturer": "生产企业全称（字符串或 null）",
  "specification": "规格，如 0.25g×12粒（字符串或 null）",
  "batch_number": "批号，字母数字组合（字符串或 null）",
  "production_date": "生产日期，格式 YYYY-MM-DD（字符串或 null）",
  "expiry_date": "有效期至，格式 YYYY-MM-DD（字符串或 null）",
  "quantity": "数量，仅整数（整数或 null）"
}
规则：
- 无法确定的字段必须填写 null，禁止猜测或捏造。
- 日期必须统一转换为 YYYY-MM-DD 格式。
- 只输出 JSON，不要有任何其他说明文字。"""


def _extract_via_llm(raw_text: str) -> Optional[dict]:
    """
    Tier 3 — DeepSeek LLM 兜底提取。
    通过 httpx 同步调用 DeepSeek Chat API（OpenAI 兼容格式）。
    API Key 从环境变量 DEEPSEEK_API_KEY 读取。
    任何网络错误或解析异常均安全返回 None，不影响主流程。
    """
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        logger.warning("[Tier 3] 未配置 DEEPSEEK_API_KEY，跳过 LLM 提取")
        return None

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": _LLM_SYSTEM_PROMPT},
            {"role": "user", "content": raw_text},
        ],
        "temperature": 0,       # 信息抽取任务关闭随机性，保证输出稳定
        "max_tokens": 512,
        "response_format": {"type": "json_object"},
    }

    try:
        with httpx.Client(timeout=15) as client:
            resp = client.post(
                "https://api.deepseek.com/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        result = json.loads(content)
        logger.info("[Tier 3] DeepSeek 提取成功：%s", result)
        return result
    except httpx.HTTPStatusError as e:
        logger.error("[Tier 3] DeepSeek API 错误 %s：%s", e.response.status_code, e.response.text)
    except Exception as e:
        logger.error("[Tier 3] DeepSeek 提取异常：%s", e)
    return None


# ============================================================
# 工具函数
# ============================================================

def _normalize_date_str(raw: str) -> Optional[str]:
    """
    将各种日期格式统一为 YYYY-MM-DD。
    任何异常输入均安全返回 None，绝不抛出异常。
    """
    if not raw:
        return None
    try:
        raw = raw.strip()
        # 将中文年月替换为分隔符，去除"日"
        cleaned = re.sub(r"[年月]", "-", raw).replace("日", "").strip("-")
        # YYYYMM 六位数字格式
        if re.fullmatch(r"\d{6}", cleaned):
            return f"{cleaned[:4]}-{cleaned[4:6]}-01"
        # YYYY-M-D / YYYY-MM / YYYY.M.D 等分隔格式
        parts = re.split(r"[-./]", cleaned)
        if len(parts) >= 2:
            year = parts[0].zfill(4)
            month = parts[1].zfill(2)
            day = parts[2].zfill(2) if len(parts) > 2 and parts[2] else "01"
            y, m, d = int(year), int(month), int(day)
            if 2000 <= y <= 2100 and 1 <= m <= 12 and 1 <= d <= 31:
                return f"{year}-{month}-{day}"
    except Exception:
        # 遇到任何无法解析的格式，静默返回 None
        pass
    return None


def _fuzzy_find_line(lines: list[str], target: str, threshold: float = 0.8) -> Optional[str]:
    """
    Tier 2 核心工具：用 difflib 在行列表中寻找与 target 最相似的行。

    仅对每行行首 len(target)*2 个字符进行比对，避免长行背景噪声干扰相似度。
    返回相似度 >= threshold 的最高匹配行，否则返回 None。
    """
    best_line: Optional[str] = None
    best_ratio = 0.0
    window = len(target) * 2

    for line in lines:
        segment = line.strip()[:window]
        ratio = difflib.SequenceMatcher(None, segment, target).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_line = line

    return best_line if best_ratio >= threshold else None


def _extract_after_colon(line: str) -> Optional[str]:
    """从行中提取冒号（中英文）或右方括号/右书名号之后的值"""
    m = re.search(r"[：:】\]]\s*(.+)", line)
    return m.group(1).strip() if m else None


# ============================================================
# 主解析函数
# ============================================================

def parse_drug_info(raw_text: str) -> ExtractedDrugData:
    """
    多级兜底策略解析药品 OCR 原始文本：
      Tier 1 → 增强型正则提取
      Tier 2 → difflib 模糊匹配（仅对正则失败的字段启动）
      Tier 3 → LLM 兜底（批号、有效期、名称均为空时触发）
    """
    text = raw_text or ""
    lines = text.splitlines()

    # ── Tier 1: 正则提取 ─────────────────────────────────────

    # 批准文号：去除 OCR 识别出的字符间多余空格
    approval: Optional[str] = None
    m = _RE_APPROVAL.search(text)
    if m:
        approval = re.sub(r"\s+", "", m.group(0))

    # 药品名称：三级降级策略
    #   1) 关键词匹配 → 2) 剂型后缀匹配 → 3) 短行兜底
    name: Optional[str] = None
    m = _RE_DRUG_NAME.search(text)
    if m:
        name = m.group(1).strip()

    if not name:
        for line in lines:
            m2 = _RE_DRUG_SUFFIX.match(line.strip())
            if m2:
                candidate = m2.group(1).strip()
                # 排除含有适应症描述性字眼的候选
                if not re.search(r"[治用于症证]", candidate):
                    name = candidate
                    break

    if not name:
        for line in lines:
            stripped = line.strip()
            if (stripped and 2 <= len(stripped) <= 15
                    and "：" not in stripped and ":" not in stripped
                    and "，" not in stripped and "。" not in stripped
                    and "、" not in stripped
                    and not re.fullmatch(r"[\d\s\-/]+", stripped)):
                name = stripped
                break

    # 剔除包装标注后缀（OTC / 外 / 处方药等）
    if name:
        name = re.sub(
            r"\s*(?:OTC外|OTC\s+外|外\s+OTC|OTC|外|处方药|非处方药|乙类|甲类)\s*$",
            "", name
        ).strip() or None

    # 批号
    batch_number: Optional[str] = None
    m = _RE_BATCH.search(text)
    if m:
        batch_number = m.group(1).strip()

    # 生产日期
    production_date: Optional[str] = None
    m = _RE_PROD_DATE.search(text)
    if m:
        production_date = _normalize_date_str(m.group(1))

    # 有效期：正向匹配优先，失败后尝试日期在关键词前的反向模式
    expiry_date: Optional[str] = None
    m = _RE_EXPIRY.search(text)
    if m:
        expiry_date = _normalize_date_str(m.group(1))
    if not expiry_date:
        m = _RE_EXPIRY_BEFORE.search(text)
        if m:
            expiry_date = _normalize_date_str(m.group(1))

    # 规格
    specification: Optional[str] = None
    m = _RE_SPEC.search(text)
    if m:
        specification = m.group(1).strip()

    # 生产企业
    manufacturer: Optional[str] = None
    m = _RE_MANUFACTURER.search(text)
    if m:
        manufacturer = m.group(1).strip()

    # 数量（取第一个命中值）
    quantity: Optional[int] = None
    m = _RE_QUANTITY.search(text)
    if m:
        quantity = int(m.group(1))

    # ── Tier 2: 模糊匹配兜底（仅对正则未命中的字段启动）────────

    if not batch_number:
        for kw in _FUZZY_KEYWORDS["batch_number"]:
            found = _fuzzy_find_line(lines, kw)
            if found:
                val = _extract_after_colon(found)
                if val:
                    bm = _RE_BATCH_VALUE.search(val)
                    if bm:
                        batch_number = bm.group(0)
                        logger.debug("[Tier 2] 批号模糊匹配成功：%s（来源行：%s）", batch_number, found.strip())
                break

    if not expiry_date:
        for kw in _FUZZY_KEYWORDS["expiry_date"]:
            found = _fuzzy_find_line(lines, kw)
            if found:
                dm = _RE_DATE_VALUE.search(found)
                if dm:
                    expiry_date = _normalize_date_str(dm.group(0))
                    if expiry_date:
                        logger.debug("[Tier 2] 有效期模糊匹配成功：%s（来源行：%s）", expiry_date, found.strip())
                break

    if not production_date:
        for kw in _FUZZY_KEYWORDS["production_date"]:
            found = _fuzzy_find_line(lines, kw)
            if found:
                dm = _RE_DATE_VALUE.search(found)
                if dm:
                    production_date = _normalize_date_str(dm.group(0))
                    if production_date:
                        logger.debug("[Tier 2] 生产日期模糊匹配成功：%s（来源行：%s）", production_date, found.strip())
                break

    if not manufacturer:
        for kw in _FUZZY_KEYWORDS["manufacturer"]:
            found = _fuzzy_find_line(lines, kw)
            if found:
                val = _extract_after_colon(found)
                if val:
                    manufacturer = val
                    logger.debug("[Tier 2] 生产企业模糊匹配成功：%s", manufacturer)
                break

    if not specification:
        for kw in _FUZZY_KEYWORDS["specification"]:
            found = _fuzzy_find_line(lines, kw)
            if found:
                val = _extract_after_colon(found)
                if val:
                    specification = val
                    logger.debug("[Tier 2] 规格模糊匹配成功：%s", specification)
                break

    # ── Tier 3: LLM 兜底（批号、有效期、名称三个核心字段均为空时触发）─

    core_fields_empty = not batch_number and not expiry_date and not name
    if core_fields_empty:
        logger.info("[Tier 3] 核心字段均为空，尝试 LLM 提取")
        llm_result = _extract_via_llm(text)
        if llm_result:
            name          = name          or llm_result.get("name")
            approval      = approval      or llm_result.get("approval_number")
            manufacturer  = manufacturer  or llm_result.get("manufacturer")
            specification = specification or llm_result.get("specification")
            batch_number  = batch_number  or llm_result.get("batch_number")
            production_date = production_date or _normalize_date_str(
                llm_result.get("production_date") or ""
            )
            expiry_date = expiry_date or _normalize_date_str(
                llm_result.get("expiry_date") or ""
            )
            if quantity is None and llm_result.get("quantity") is not None:
                try:
                    quantity = int(llm_result["quantity"])
                except (ValueError, TypeError):
                    pass

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

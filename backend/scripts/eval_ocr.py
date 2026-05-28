"""
OCR 识别精度评测脚本（本地手动运行）

用法：
  1. 把药盒图放入 backend/tests/ocr_eval/images/
  2. 参照 ground_truth.example.json 创建 ground_truth.json，
     键为图片文件名，值为人工标注的正确字段。
  3. 在 backend/ 目录下运行：python scripts/eval_ocr.py

脚本对每张图跑完整识别流水线，逐字段与标注比对，输出准确率。
会真实调用 qwen-vl-ocr 产生少量费用；不进 CI。
"""
import asyncio
import json
import sys
from pathlib import Path

# 确保能 import app 包
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ocr.pipeline import recognize_and_extract  # noqa: E402

_EVAL_DIR = Path(__file__).resolve().parent.parent / "tests" / "ocr_eval"
_IMAGES_DIR = _EVAL_DIR / "images"
_GROUND_TRUTH = _EVAL_DIR / "ground_truth.json"

_FIELDS = (
    "name", "approval_number", "manufacturer", "specification",
    "batch_number", "production_date", "expiry_date", "quantity",
)


def _norm(value) -> str:
    """归一化字段值用于比对：转字符串、去首尾空白"""
    if value is None:
        return ""
    return str(value).strip()


def _score_field(predicted, expected) -> bool:
    """单字段是否命中（归一化后完全相等）"""
    return _norm(predicted) == _norm(expected)


def _aggregate(per_image: list[dict]) -> dict:
    """汇总逐图结果，算每字段与总体准确率"""
    field_hits = {f: 0 for f in _FIELDS}
    field_total = {f: 0 for f in _FIELDS}
    for row in per_image:
        for f in _FIELDS:
            if f not in row["expected"]:
                continue
            field_total[f] += 1
            if row["fields"].get(f):
                field_hits[f] += 1

    report: dict = {}
    for f in _FIELDS:
        total = field_total[f]
        report[f] = {
            "hits": field_hits[f],
            "total": total,
            "accuracy": round(field_hits[f] / total, 3) if total else None,
        }
    all_hits = sum(field_hits.values())
    all_total = sum(field_total.values())
    report["_overall"] = {
        "hits": all_hits,
        "total": all_total,
        "accuracy": round(all_hits / all_total, 3) if all_total else None,
    }
    return report


async def _evaluate() -> int:
    if not _GROUND_TRUTH.exists():
        print(f"未找到标注文件：{_GROUND_TRUTH}")
        print("请参照 ground_truth.example.json 创建 ground_truth.json")
        return 1

    ground_truth = json.loads(_GROUND_TRUTH.read_text(encoding="utf-8"))
    if not ground_truth:
        print("标注文件为空，无可评测样本")
        return 1

    per_image: list[dict] = []
    for filename, expected in ground_truth.items():
        image_path = _IMAGES_DIR / filename
        if not image_path.exists():
            print(f"[跳过] 图片不存在：{filename}")
            continue
        result = await recognize_and_extract(image_path.read_bytes())
        predicted = result.extracted.model_dump()
        fields = {f: _score_field(predicted.get(f), expected.get(f)) for f in expected}
        per_image.append({"filename": filename, "expected": expected, "fields": fields})
        hit = sum(1 for v in fields.values() if v)
        print(f"[{filename}] 命中 {hit}/{len(fields)}  完整度={result.confidence}")

    if not per_image:
        print("没有可评测的图片（检查 images/ 目录与标注文件名是否一致）")
        return 1

    report = _aggregate(per_image)
    print("\n===== 逐字段准确率 =====")
    for f in _FIELDS:
        r = report[f]
        if r["total"]:
            print(f"  {f:<18} {r['hits']}/{r['total']}  准确率 {r['accuracy']}")
    overall = report["_overall"]
    print(f"\n总体准确率：{overall['hits']}/{overall['total']} = {overall['accuracy']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_evaluate()))

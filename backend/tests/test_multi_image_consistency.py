from app.ocr.multi_image_consistency import (
    ImageOcrEvidence,
    LlmConsistencyJudgement,
    evaluate_multi_image_consistency,
)


def test_approval_number_conflict_fails():
    result = evaluate_multi_image_consistency([
        ImageOcrEvidence(image_index=1, raw_text="A", fields={"approval_number": "国药准字A"}),
        ImageOcrEvidence(image_index=2, raw_text="B", fields={"approval_number": "国药准字B"}),
    ])

    assert result.status == "failed"
    assert result.review_required is False
    assert result.batch_confirm_allowed is False
    assert result.conflicts[0]["field"] == "approval_number"
    assert "批准文号" in result.message


def test_complementary_fields_merge_with_review_when_no_overlap():
    result = evaluate_multi_image_consistency([
        ImageOcrEvidence(image_index=1, raw_text="名称", fields={"name": "药品甲"}),
        ImageOcrEvidence(image_index=2, raw_text="有效期", fields={"expiry_date": "2026-01-01"}),
    ])

    assert result.status == "review_required"
    assert result.review_required is True
    assert result.batch_confirm_allowed is False
    assert result.merged_fields["name"] == "药品甲"
    assert result.merged_fields["expiry_date"] == "2026-01-01"
    assert result.merged_from_image_indexes["name"] == 1
    assert result.merged_from_image_indexes["expiry_date"] == 2
    assert "[图片1]" in result.raw_text
    assert "[图片2]" in result.raw_text


def test_same_approval_number_passes_without_review():
    result = evaluate_multi_image_consistency([
        ImageOcrEvidence(image_index=1, raw_text="批准文号", fields={"approval_number": "国药准字H1"}),
        ImageOcrEvidence(image_index=2, raw_text="批准文号", fields={"approval_number": "国药准字 H1"}),
    ])

    assert result.status == "passed"
    assert result.review_required is False
    assert result.batch_confirm_allowed is True
    assert result.merged_fields["approval_number"] == "国药准字H1"
    assert result.merged_from_image_indexes["approval_number"] == 1


def test_batch_number_conflict_fails_as_possible_different_batch():
    result = evaluate_multi_image_consistency([
        ImageOcrEvidence(image_index=1, raw_text="批号A", fields={"batch_number": "BATCH-A"}),
        ImageOcrEvidence(image_index=2, raw_text="批号B", fields={"batch_number": "BATCH-B"}),
    ])

    assert result.status == "failed"
    assert result.conflicts[0]["field"] == "batch_number"
    assert "不同批次" in result.message


def test_soft_identity_conflicts_require_manual_review_not_rule_failure():
    result = evaluate_multi_image_consistency([
        ImageOcrEvidence(
            image_index=1,
            raw_text="克洛己新干混悬剂\n江苏正大清江制药有限公司\n9袋/盒",
            fields={
                "name": "克洛己新干混悬剂",
                "manufacturer": "江苏正大清江制药有限公司",
                "specification": "9袋/盒",
            },
        ),
        ImageOcrEvidence(
            image_index=2,
            raw_text="金振口服液\n海南亚洲制药股份有限公司\n10ml/支",
            fields={
                "name": "金振口服液",
                "manufacturer": "海南亚洲制药股份有限公司",
                "specification": "10ml/支",
            },
        ),
    ])

    assert result.status == "review_required"
    assert result.method == "rule_soft_conflict"
    assert result.review_required is True
    assert result.batch_confirm_allowed is False
    assert {conflict["field"] for conflict in result.conflicts} == {
        "name",
        "manufacturer",
        "specification",
    }
    assert "人工核对" in result.message


def test_soft_identity_conflicts_llm_unlikely_fails():
    result = evaluate_multi_image_consistency(
        [
            ImageOcrEvidence(image_index=1, raw_text="A", fields={"name": "药品甲"}),
            ImageOcrEvidence(image_index=2, raw_text="B", fields={"name": "药品乙"}),
        ],
        llm_judgement=LlmConsistencyJudgement(
            same_drug="unlikely",
            confidence=0.8,
            decision="fail",
            reason="AI 判断疑似不同药品",
            evidence=[],
            risk_notes=[],
        ),
    )

    assert result.status == "failed"
    assert result.method == "llm_soft_conflict"
    assert "不同药品" in result.message


def test_soft_identity_conflicts_llm_error_reports_llm_failure():
    result = evaluate_multi_image_consistency(
        [
            ImageOcrEvidence(image_index=1, raw_text="A", fields={"name": "药品甲"}),
            ImageOcrEvidence(image_index=2, raw_text="B", fields={"name": "药品乙"}),
        ],
        llm_error="ReadTimeout",
    )

    assert result.status == "review_required"
    assert result.method == "llm_soft_conflict"
    assert "LLM 调用失败" in result.message
    assert "AI 仅提供辅助意见" not in result.message
    assert result.llm_error == "ReadTimeout"


def test_no_overlap_llm_unlikely_fails():
    result = evaluate_multi_image_consistency(
        [
            ImageOcrEvidence(image_index=1, raw_text="名称", fields={"name": "药品甲"}),
            ImageOcrEvidence(image_index=2, raw_text="厂家", fields={"manufacturer": "厂家乙"}),
        ],
        llm_judgement=LlmConsistencyJudgement(
            same_drug="unlikely",
            confidence=0.8,
            decision="fail",
            reason="疑似不同药品",
            evidence=[],
            risk_notes=["缺少共同字段"],
        ),
    )

    assert result.status == "failed"
    assert result.review_required is False
    assert "疑似不同药品" in result.message
    assert result.llm_judgement is not None


def test_no_overlap_llm_error_reports_llm_failure():
    result = evaluate_multi_image_consistency(
        [
            ImageOcrEvidence(image_index=1, raw_text="名称", fields={"name": "药品甲"}),
            ImageOcrEvidence(image_index=2, raw_text="厂家", fields={"manufacturer": "厂家甲"}),
        ],
        llm_error="ReadTimeout",
    )

    assert result.status == "review_required"
    assert result.method == "llm_no_overlap"
    assert "LLM 调用失败" in result.message
    assert result.llm_error == "ReadTimeout"


def test_no_overlap_llm_likely_still_requires_manual_review():
    result = evaluate_multi_image_consistency(
        [
            ImageOcrEvidence(image_index=1, raw_text="名称", fields={"name": "药品甲"}),
            ImageOcrEvidence(image_index=2, raw_text="厂家", fields={"manufacturer": "厂家乙"}),
        ],
        llm_judgement=LlmConsistencyJudgement(
            same_drug="likely",
            confidence=0.74,
            decision="pass",
            reason="未发现冲突",
            evidence=["图片1有名称", "图片2有厂家"],
            risk_notes=["缺少共同字段"],
        ),
    )

    assert result.status == "review_required"
    assert result.review_required is True
    assert result.batch_confirm_allowed is False
    assert result.llm_judgement["same_drug"] == "likely"

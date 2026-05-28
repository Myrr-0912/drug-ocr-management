from scripts.eval_ocr import _aggregate, _norm, _score_field


def test_norm_handles_none_and_whitespace():
    assert _norm(None) == ""
    assert _norm("  20240315 ") == "20240315"
    assert _norm(12) == "12"


def test_score_field_matches_after_normalization():
    assert _score_field("20240315", " 20240315 ") is True
    assert _score_field(1, "1") is True
    assert _score_field("A", "B") is False


def test_aggregate_computes_field_and_overall_accuracy():
    per_image = [
        {
            "filename": "a.jpg",
            "expected": {"name": "药A", "batch_number": "B1"},
            "fields": {"name": True, "batch_number": False},
        },
        {
            "filename": "b.jpg",
            "expected": {"name": "药B", "batch_number": "B2"},
            "fields": {"name": True, "batch_number": True},
        },
    ]
    report = _aggregate(per_image)
    assert report["name"]["hits"] == 2
    assert report["name"]["total"] == 2
    assert report["name"]["accuracy"] == 1.0
    assert report["batch_number"]["hits"] == 1
    assert report["batch_number"]["accuracy"] == 0.5
    assert report["_overall"]["hits"] == 3
    assert report["_overall"]["total"] == 4
    assert report["_overall"]["accuracy"] == 0.75

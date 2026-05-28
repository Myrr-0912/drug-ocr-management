from app.config import Settings


def test_ocr_settings_have_defaults(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("JWT_SECRET_KEY", "x" * 40)
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("QWEN_OCR_MODEL", raising=False)
    s = Settings()
    assert s.dashscope_api_key == ""
    assert s.qwen_ocr_model == "qwen-vl-ocr-latest"
    assert s.qwen_ocr_timeout_seconds == 120
    assert s.qwen_ocr_max_attempts == 2
    assert s.qwen_ocr_max_pixels == 4194304
    assert s.ocr_preprocess_min_short_edge == 800
    assert s.ocr_preprocess_target_short_edge == 1200
    assert s.ocr_preprocess_jpeg_quality == 85


def test_old_aliyun_ocr_settings_removed():
    # 直接查类的字段注册表，语义无歧义、无需实例化
    assert "aliyun_ocr_access_key_id" not in Settings.model_fields
    assert "deepseek_api_key" not in Settings.model_fields

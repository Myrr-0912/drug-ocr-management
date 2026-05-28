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
    assert s.qwen_ocr_max_pixels == 2097152
    assert s.qwen_ocr_per_record_concurrency == 2
    assert s.qwen_ocr_global_concurrency == 3
    assert s.ocr_preprocess_min_short_edge == 800
    assert s.ocr_preprocess_target_short_edge == 900
    assert s.ocr_preprocess_jpeg_quality == 75
    assert s.max_ocr_images_per_record == 6
    assert s.aliyun_oss_endpoint == ""
    assert s.aliyun_oss_bucket == ""
    assert s.aliyun_oss_access_key_id == ""
    assert s.aliyun_oss_access_key_secret == ""
    assert s.aliyun_oss_ocr_prefix == "ocr/qwen"
    assert s.aliyun_oss_signed_url_expire_seconds == 1800
    assert s.deepseek_api_key == ""
    assert s.deepseek_base_url == "https://api.deepseek.com"
    assert s.deepseek_model == "deepseek-v4-flash"
    assert s.deepseek_timeout_seconds == 30


def test_old_aliyun_ocr_settings_removed_but_deepseek_auxiliary_kept():
    # 直接查类的字段注册表，语义无歧义、无需实例化
    assert "aliyun_ocr_access_key_id" not in Settings.model_fields
    assert "deepseek_api_key" in Settings.model_fields

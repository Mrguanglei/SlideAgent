from utils.env_config import env_config


def test_unified_model_config_ignores_legacy_overrides(monkeypatch):
    monkeypatch.setenv("PPTAGENT_MODEL", "gemini-3-pro-high")
    monkeypatch.setenv("PPTAGENT_API_BASE", "http://pptagent-base/v1")
    monkeypatch.setenv("PPTAGENT_API_KEY", "pptagent-key")

    # Legacy split-route variables should not affect effective runtime config.
    monkeypatch.setenv("DESIGN_AGENT_MODEL", "legacy-design-model")
    monkeypatch.setenv("DESIGN_AGENT_BASE_URL", "http://legacy-design/v1")
    monkeypatch.setenv("DESIGN_AGENT_API_KEY", "legacy-design-key")
    # Image reference model is intentionally allowed to override for multimodal support.
    monkeypatch.setenv("IMAGE_REFERENCE_MODEL", "multimodal-image-model")
    monkeypatch.setenv("IMAGE_REFERENCE_BASE_URL", "http://legacy-image/v1")
    monkeypatch.setenv("IMAGE_REFERENCE_API_KEY", "legacy-image-key")
    monkeypatch.setenv("KNOWLEDGE_LLM_MODEL", "legacy-knowledge-model")
    monkeypatch.setenv("KNOWLEDGE_LLM_BASE_URL", "http://legacy-knowledge/v1")
    monkeypatch.setenv("KNOWLEDGE_LLM_API_KEY", "legacy-knowledge-key")

    env_config.load(force=True)

    assert env_config.PPTAGENT_MODEL == "gemini-3-pro-high"
    assert env_config.DESIGN_AGENT_MODEL == env_config.PPTAGENT_MODEL
    assert env_config.IMAGE_REFERENCE_MODEL == "multimodal-image-model"
    assert env_config.KNOWLEDGE_LLM_MODEL == env_config.PPTAGENT_MODEL

    assert env_config.DESIGN_AGENT_BASE_URL == env_config.PPTAGENT_API_BASE
    assert env_config.IMAGE_REFERENCE_BASE_URL == env_config.PPTAGENT_API_BASE
    assert env_config.KNOWLEDGE_LLM_BASE_URL == env_config.PPTAGENT_API_BASE

    assert env_config.DESIGN_AGENT_API_KEY == env_config.PPTAGENT_API_KEY
    assert env_config.IMAGE_REFERENCE_API_KEY == env_config.PPTAGENT_API_KEY
    assert env_config.KNOWLEDGE_LLM_API_KEY == env_config.PPTAGENT_API_KEY


def test_image_reference_model_falls_back_to_pptagent(monkeypatch):
    monkeypatch.setenv("PPTAGENT_MODEL", "gemini-3-pro-high")
    monkeypatch.setenv("PPTAGENT_API_BASE", "http://pptagent-base/v1")
    monkeypatch.setenv("PPTAGENT_API_KEY", "pptagent-key")
    monkeypatch.delenv("IMAGE_REFERENCE_MODEL", raising=False)

    env_config.load(force=True)

    assert env_config.IMAGE_REFERENCE_MODEL == env_config.PPTAGENT_MODEL

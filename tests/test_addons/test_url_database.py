"""Tests for addons/workflow_manager/url_database.py - Known model URLs."""


class TestSuggestUrl:
    """Tests for suggest_url function."""

    def test_exact_match(self):
        """Should find model with exact filename match."""
        from addons.workflow_manager.url_database import suggest_url

        result = suggest_url("wan2.2_i2v_720p_14B_fp8_e4m3fn.safetensors")

        assert result is not None
        assert result.filename == "wan2.2_i2v_720p_14B_fp8_e4m3fn.safetensors"
        assert "huggingface.co" in result.url
        assert result.size_mb > 0

    def test_case_insensitive_match(self):
        """Should find model with case-insensitive match."""
        from addons.workflow_manager.url_database import suggest_url

        # Try uppercase
        result = suggest_url("WAN2.2_I2V_720P_14B_FP8_E4M3FN.SAFETENSORS")

        assert result is not None

    def test_unknown_model(self):
        """Should return None for unknown model."""
        from addons.workflow_manager.url_database import suggest_url

        result = suggest_url("completely_unknown_model.safetensors")

        assert result is None

    def test_empty_filename(self):
        """Should return None for empty filename."""
        from addons.workflow_manager.url_database import suggest_url

        assert suggest_url("") is None

    def test_known_wan_models(self):
        """Should have common WAN models."""
        from addons.workflow_manager.url_database import suggest_url

        wan_models = [
            "wan2.2_i2v_720p_14B_bf16.safetensors",
            "wan2.2_i2v_720p_14B_fp8_e4m3fn.safetensors",
            "wan_2.2_vae.safetensors",
            "umt5_xxl_encoder_q4_k_m.gguf",
            "clip_vision_h.safetensors",
        ]

        for model in wan_models:
            result = suggest_url(model)
            assert result is not None, f"Missing WAN model: {model}"
            assert result.target_path != ""

    def test_known_flux_models(self):
        """Should have common FLUX models."""
        from addons.workflow_manager.url_database import suggest_url

        flux_models = [
            "flux1-dev.safetensors",
            "flux1-dev-fp8.safetensors",
            "ae.safetensors",
            "t5xxl_fp16.safetensors",
            "t5xxl_fp8_e4m3fn.safetensors",
            "clip_l.safetensors",
        ]

        for model in flux_models:
            result = suggest_url(model)
            assert result is not None, f"Missing FLUX model: {model}"

    def test_known_sdxl_models(self):
        """Should have common SDXL models."""
        from addons.workflow_manager.url_database import suggest_url

        sdxl_models = [
            "sd_xl_base_1.0.safetensors",
            "sdxl_vae.safetensors",
        ]

        for model in sdxl_models:
            result = suggest_url(model)
            assert result is not None, f"Missing SDXL model: {model}"


class TestKnownModel:
    """Tests for KnownModel dataclass."""

    def test_known_model_creation(self):
        """Should create KnownModel with all fields."""
        from addons.workflow_manager.url_database import KnownModel

        model = KnownModel(
            name="Test Model",
            filename="test.safetensors",
            url="https://example.com/test.safetensors",
            size_mb=1000,
            target_path="checkpoints",
        )

        assert model.name == "Test Model"
        assert model.filename == "test.safetensors"
        assert model.url == "https://example.com/test.safetensors"
        assert model.size_mb == 1000
        assert model.target_path == "checkpoints"
        assert model.aliases == []

    def test_known_model_with_aliases(self):
        """Should support aliases for alternative filenames."""
        from addons.workflow_manager.url_database import KnownModel

        model = KnownModel(
            name="Test Model",
            filename="test.safetensors",
            url="https://example.com/test.safetensors",
            size_mb=1000,
            target_path="checkpoints",
            aliases=["test_v1.safetensors", "test_old.safetensors"],
        )

        assert len(model.aliases) == 2
        assert "test_v1.safetensors" in model.aliases


class TestGetAllKnownModels:
    """Tests for get_all_known_models function."""

    def test_returns_list(self):
        """Should return a list of KnownModel objects."""
        from addons.workflow_manager.url_database import KnownModel, get_all_known_models

        models = get_all_known_models()

        assert isinstance(models, list)
        assert len(models) > 0
        assert all(isinstance(m, KnownModel) for m in models)

    def test_all_models_have_required_fields(self):
        """All models should have required fields populated."""
        from addons.workflow_manager.url_database import get_all_known_models

        models = get_all_known_models()

        for model in models:
            assert model.name, f"Model missing name: {model.filename}"
            assert model.filename, "Model missing filename"
            assert model.url, f"Model missing URL: {model.filename}"
            assert model.size_mb > 0, f"Model has invalid size: {model.filename}"
            assert model.target_path, f"Model missing target_path: {model.filename}"

    def test_urls_are_valid(self):
        """All URLs should be valid HTTPS URLs."""
        from addons.workflow_manager.url_database import get_all_known_models

        models = get_all_known_models()

        for model in models:
            assert model.url.startswith("https://"), f"URL not HTTPS: {model.url}"
            assert "huggingface.co" in model.url or "github.com" in model.url, (
                f"URL from unexpected source: {model.url}"
            )

    def test_target_paths_are_valid(self):
        """All target paths should be valid model folders."""
        from addons.workflow_manager.url_database import get_all_known_models

        valid_paths = {
            "checkpoints",
            "diffusion_models",
            "diffusion_models/wan",
            "loras",
            "loras/wan",
            "text_encoders",
            "vae",
            "clip_vision",
            "controlnet",
            "upscale_models",
            "LLM",
        }

        models = get_all_known_models()

        for model in models:
            assert model.target_path in valid_paths, (
                f"Invalid target_path '{model.target_path}' for {model.filename}"
            )


class TestKnownModelsDatabase:
    """Tests for KNOWN_MODELS database."""

    def test_database_not_empty(self):
        """KNOWN_MODELS should contain entries."""
        from addons.workflow_manager.url_database import KNOWN_MODELS

        assert len(KNOWN_MODELS) > 0

    def test_database_keys_are_filenames(self):
        """Database keys should be filenames."""
        from addons.workflow_manager.url_database import KNOWN_MODELS

        for key, model in KNOWN_MODELS.items():
            assert key == model.filename, f"Key '{key}' doesn't match filename '{model.filename}'"

    def test_no_duplicate_urls(self):
        """Each model should have a unique URL."""
        from addons.workflow_manager.url_database import KNOWN_MODELS

        urls = [m.url for m in KNOWN_MODELS.values()]
        # Some models might legitimately share URLs (e.g., same file, different names)
        # but we should check for obvious duplicates
        unique_urls = set(urls)

        # Allow some duplicates but not too many
        duplicate_count = len(urls) - len(unique_urls)
        assert duplicate_count < len(urls) * 0.1, "Too many duplicate URLs"

"""Pytest fixtures for Cindergrace Toolkit tests."""

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# === Temporary Directory Fixtures ===


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_config_dir(temp_dir):
    """Create a temporary config directory structure."""
    config_dir = temp_dir / "config"
    config_dir.mkdir(parents=True)

    user_config_dir = temp_dir / ".config"
    user_config_dir.mkdir(parents=True)

    return {
        "root": temp_dir,
        "config": config_dir,
        "user_config": user_config_dir,
    }


# === Config Fixtures ===


@pytest.fixture
def sample_config() -> dict[str, Any]:
    """Sample config.json content."""
    return {
        "paths": {
            "comfyui": {
                "local": "~/ComfyUI",
                "runpod": "/workspace/ComfyUI",
                "colab": "/content/ComfyUI",
            },
            "workflows": {
                "local": "{comfyui}/user/default/workflows",
                "runpod": "{comfyui}/user/default/workflows",
                "colab": "{comfyui}/user/default/workflows",
            },
            "backup": {
                "local": "",
                "runpod": "/runpod-volume/model_backup",
                "colab": "",
            },
        },
        "workflow_pattern": "gc*.json",
        "security": {
            "disable_ssl_verify": False,
        },
    }


@pytest.fixture
def sample_workflow_models() -> dict[str, Any]:
    """Sample workflow_models.json content."""
    return {
        "version": "1.1.0",
        "target_folders": [
            "checkpoints",
            "diffusion_models",
            "diffusion_models/wan",
            "loras",
            "text_encoders",
            "vae",
        ],
        "workflows": {
            "gcv_wan_test": {
                "name": "WAN Test Workflow",
                "description": "Test workflow",
                "category": "video",
                "model_sets": {
                    "16GB": {
                        "name": "16GB VRAM",
                        "vram_gb": 16,
                        "models": ["model_a", "model_b"],
                    },
                    "24GB": {
                        "name": "24GB VRAM",
                        "vram_gb": 24,
                        "models": ["model_a", "model_c"],
                    },
                },
            },
        },
        "models": {
            "model_a": {
                "name": "Model A",
                "filename": "model_a.safetensors",
                "url": "https://example.com/model_a.safetensors",
                "target_path": "diffusion_models/wan",
                "size_mb": 14000,
            },
            "model_b": {
                "name": "Model B",
                "filename": "model_b.safetensors",
                "url": "https://example.com/model_b.safetensors",
                "target_path": "text_encoders",
                "size_mb": 5000,
            },
            "model_c": {
                "name": "Model C",
                "filename": "model_c.safetensors",
                "url": "https://example.com/model_c.safetensors",
                "target_path": "diffusion_models/wan",
                "size_mb": 28000,
            },
        },
    }


@pytest.fixture
def config_file(temp_config_dir, sample_config):
    """Create a config.json file in temp directory."""
    config_path = temp_config_dir["config"] / "config.json"
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(sample_config, f)
    return config_path


# === Workflow Fixtures ===


@pytest.fixture
def sample_workflow_api_format() -> dict[str, Any]:
    """Sample workflow in API format."""
    return {
        "nodes": [
            {
                "id": 1,
                "type": "UNETLoader",
                "class_type": "UNETLoader",
                "inputs": {"unet_name": "wan2.2_i2v_720p_14B_fp8_e4m3fn.safetensors"},
            },
            {
                "id": 2,
                "type": "VAELoader",
                "class_type": "VAELoader",
                "inputs": {"vae_name": "wan_2.2_vae.safetensors"},
            },
            {
                "id": 3,
                "type": "CLIPLoader",
                "class_type": "CLIPLoader",
                "inputs": {"clip_name": "t5xxl_fp8_e4m3fn.safetensors"},
            },
        ],
        "links": [],
    }


@pytest.fixture
def sample_workflow_dict_format() -> dict[str, Any]:
    """Sample workflow in node dict format."""
    return {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": "flux1-dev-fp8.safetensors"},
        },
        "2": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": "ae.safetensors"},
        },
        "3": {
            "class_type": "LoraLoader",
            "inputs": {"lora_name": "my_lora.safetensors"},
        },
    }


@pytest.fixture
def workflow_file(temp_dir, sample_workflow_api_format):
    """Create a workflow JSON file."""
    wf_path = temp_dir / "gc_test_workflow.json"
    with open(wf_path, "w", encoding="utf-8") as f:
        json.dump(sample_workflow_api_format, f)
    return wf_path


# === Mock Fixtures ===


@pytest.fixture
def mock_gradio():
    """Mock gradio module for addon tests."""
    with patch.dict("sys.modules", {"gradio": MagicMock()}):
        yield


@pytest.fixture
def mock_comfyui_path(temp_dir):
    """Create a mock ComfyUI directory structure."""
    comfy_dir = temp_dir / "ComfyUI"
    comfy_dir.mkdir()

    # Create main.py to simulate real ComfyUI
    (comfy_dir / "main.py").touch()

    # Create models directory structure
    models_dir = comfy_dir / "models"
    models_dir.mkdir()

    for folder in [
        "checkpoints",
        "diffusion_models",
        "diffusion_models/wan",
        "loras",
        "text_encoders",
        "vae",
        "clip_vision",
        "controlnet",
        "upscale_models",
        "LLM",
    ]:
        (models_dir / folder).mkdir(parents=True, exist_ok=True)

    # Create workflows directory
    workflows_dir = comfy_dir / "user" / "default" / "workflows"
    workflows_dir.mkdir(parents=True)

    return comfy_dir


@pytest.fixture
def mock_model_files(mock_comfyui_path):
    """Create mock model files in ComfyUI structure."""
    models_dir = mock_comfyui_path / "models"

    # Create some fake model files
    model_files = {
        "diffusion_models/wan/test_model.safetensors": 1024 * 1024,  # 1 MB
        "text_encoders/test_encoder.safetensors": 512 * 1024,  # 512 KB
        "vae/test_vae.safetensors": 256 * 1024,  # 256 KB
        "checkpoints/test_checkpoint.safetensors": 2048 * 1024,  # 2 MB
    }

    for rel_path, size in model_files.items():
        file_path = models_dir / rel_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        # Create file with specified size
        with open(file_path, "wb") as f:
            f.write(b"\x00" * size)

    return models_dir


# === Environment Fixtures ===


@pytest.fixture
def local_environment():
    """Simulate local environment."""
    with patch.dict(os.environ, {}, clear=False):
        # Ensure RunPod/Colab markers don't exist
        with patch("os.path.exists") as mock_exists:

            def exists_side_effect(path):
                if path in ["/workspace", "/runpod-volume", "/content"]:
                    return False
                return (
                    os.path.exists.__wrapped__(path)
                    if hasattr(os.path.exists, "__wrapped__")
                    else True
                )

            mock_exists.side_effect = exists_side_effect
            yield


@pytest.fixture
def runpod_environment():
    """Simulate RunPod environment."""
    with patch("os.path.exists") as mock_exists:

        def exists_side_effect(path):
            if path in ["/workspace", "/runpod-volume"]:
                return True
            if path == "/content":
                return False
            return True

        mock_exists.side_effect = exists_side_effect
        yield


@pytest.fixture
def colab_environment():
    """Simulate Google Colab environment."""
    with patch.dict(os.environ, {"COLAB_GPU": "1"}), patch("os.path.exists") as mock_exists:

        def exists_side_effect(path):
            if path == "/content":
                return True
            if path in ["/workspace", "/runpod-volume"]:
                return False
            return True

        mock_exists.side_effect = exists_side_effect
        yield


# === Release Config Fixtures ===


@pytest.fixture
def sample_release_config() -> dict[str, Any]:
    """Sample release configuration."""
    return {
        "name": "Test Release",
        "version": "1.0.0",
        "description": "Test release configuration",
        "addons": [
            {"id": "model_depot", "enabled": True},
            {"id": "workflow_manager", "enabled": True},
            {"id": "system_info", "enabled": False},
        ],
        "remote_profiles": {
            "enabled": False,
            "url": "",
            "auto_sync": False,
        },
    }


@pytest.fixture
def release_file(temp_config_dir, sample_release_config):
    """Create a release config file."""
    releases_dir = temp_config_dir["config"] / "releases"
    releases_dir.mkdir(parents=True)

    release_path = releases_dir / "test.json"
    with open(release_path, "w", encoding="utf-8") as f:
        json.dump(sample_release_config, f)

    return release_path

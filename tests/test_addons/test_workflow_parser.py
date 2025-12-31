"""Tests for addons/workflow_manager/workflow_parser.py - Workflow parsing."""

import json
from pathlib import Path

import pytest


class TestParseWorkflow:
    """Tests for parse_workflow function."""

    def test_parse_api_format(self, workflow_file):
        """Should parse workflow in API format (nodes array)."""
        from addons.workflow_manager.workflow_parser import parse_workflow

        models = parse_workflow(workflow_file)

        assert len(models) == 3
        filenames = [m.filename for m in models]
        assert "wan2.2_i2v_720p_14B_fp8_e4m3fn.safetensors" in filenames
        assert "wan_2.2_vae.safetensors" in filenames
        assert "t5xxl_fp8_e4m3fn.safetensors" in filenames

    def test_parse_dict_format(self, temp_dir, sample_workflow_dict_format):
        """Should parse workflow in dict format (numbered keys)."""
        wf_path = temp_dir / "dict_workflow.json"
        with open(wf_path, "w") as f:
            json.dump(sample_workflow_dict_format, f)

        from addons.workflow_manager.workflow_parser import parse_workflow

        models = parse_workflow(wf_path)

        assert len(models) == 3
        filenames = [m.filename for m in models]
        assert "flux1-dev-fp8.safetensors" in filenames
        assert "ae.safetensors" in filenames
        assert "my_lora.safetensors" in filenames

    def test_parse_nonexistent_file(self, temp_dir):
        """Should return empty list for non-existent file."""
        from addons.workflow_manager.workflow_parser import parse_workflow

        result = parse_workflow(temp_dir / "nonexistent.json")
        assert result == []

    def test_parse_invalid_json(self, temp_dir):
        """Should handle invalid JSON gracefully."""
        wf_path = temp_dir / "invalid.json"
        with open(wf_path, "w") as f:
            f.write("not valid json {{{")

        from addons.workflow_manager.workflow_parser import parse_workflow

        result = parse_workflow(wf_path)
        assert result == []

    def test_parse_empty_workflow(self, temp_dir):
        """Should handle workflow with no model loaders."""
        wf_path = temp_dir / "empty.json"
        with open(wf_path, "w") as f:
            json.dump({"nodes": []}, f)

        from addons.workflow_manager.workflow_parser import parse_workflow

        result = parse_workflow(wf_path)
        assert result == []

    def test_target_path_mapping(self, temp_dir):
        """Should map node types to correct target paths."""
        workflow = {
            "nodes": [
                {"id": 1, "class_type": "UNETLoader", "inputs": {"unet_name": "unet.safetensors"}},
                {"id": 2, "class_type": "VAELoader", "inputs": {"vae_name": "vae.safetensors"}},
                {"id": 3, "class_type": "LoraLoader", "inputs": {"lora_name": "lora.safetensors"}},
                {"id": 4, "class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "ckpt.safetensors"}},
                {"id": 5, "class_type": "CLIPVisionLoader", "inputs": {"clip_name": "clip.safetensors"}},
            ]
        }
        wf_path = temp_dir / "paths.json"
        with open(wf_path, "w") as f:
            json.dump(workflow, f)

        from addons.workflow_manager.workflow_parser import parse_workflow

        models = parse_workflow(wf_path)
        path_map = {m.filename: m.target_path for m in models}

        assert path_map["unet.safetensors"] == "diffusion_models"
        assert path_map["vae.safetensors"] == "vae"
        assert path_map["lora.safetensors"] == "loras"
        assert path_map["ckpt.safetensors"] == "checkpoints"
        assert path_map["clip.safetensors"] == "clip_vision"

    def test_wan_models_special_path(self, temp_dir):
        """WAN models should map to diffusion_models/wan."""
        workflow = {
            "nodes": [
                {"id": 1, "class_type": "WanI2VLoader", "inputs": {"model": "wan_model.safetensors"}},
            ]
        }
        wf_path = temp_dir / "wan.json"
        with open(wf_path, "w") as f:
            json.dump(workflow, f)

        from addons.workflow_manager.workflow_parser import parse_workflow

        models = parse_workflow(wf_path)
        assert len(models) == 1
        assert models[0].target_path == "diffusion_models/wan"

    def test_deduplicate_models(self, temp_dir):
        """Should not return duplicate filenames."""
        workflow = {
            "nodes": [
                {"id": 1, "class_type": "VAELoader", "inputs": {"vae_name": "shared.safetensors"}},
                {"id": 2, "class_type": "VAELoader", "inputs": {"vae_name": "shared.safetensors"}},
                {"id": 3, "class_type": "VAELoader", "inputs": {"vae_name": "shared.safetensors"}},
            ]
        }
        wf_path = temp_dir / "dupes.json"
        with open(wf_path, "w") as f:
            json.dump(workflow, f)

        from addons.workflow_manager.workflow_parser import parse_workflow

        models = parse_workflow(wf_path)
        assert len(models) == 1

    def test_widgets_values_fallback(self, temp_dir):
        """Should read model name from widgets_values if inputs missing."""
        workflow = {
            "nodes": [
                {
                    "id": 1,
                    "class_type": "UNETLoader",
                    "inputs": {},
                    "widgets_values": ["model_from_widget.safetensors"],
                },
            ]
        }
        wf_path = temp_dir / "widgets.json"
        with open(wf_path, "w") as f:
            json.dump(workflow, f)

        from addons.workflow_manager.workflow_parser import parse_workflow

        models = parse_workflow(wf_path)
        assert len(models) == 1
        assert models[0].filename == "model_from_widget.safetensors"

    def test_dual_clip_loader(self, temp_dir):
        """DualCLIPLoader should capture both clip names."""
        workflow = {
            "nodes": [
                {
                    "id": 1,
                    "class_type": "DualCLIPLoader",
                    "inputs": {
                        "clip_name1": "clip1.safetensors",
                        "clip_name2": "clip2.safetensors",
                    },
                },
            ]
        }
        wf_path = temp_dir / "dual_clip.json"
        with open(wf_path, "w") as f:
            json.dump(workflow, f)

        from addons.workflow_manager.workflow_parser import parse_workflow

        models = parse_workflow(wf_path)
        filenames = [m.filename for m in models]

        assert "clip1.safetensors" in filenames
        assert "clip2.safetensors" in filenames


class TestParseWorkflowFromDict:
    """Tests for parse_workflow_from_dict function."""

    def test_parse_from_dict(self, sample_workflow_api_format):
        """Should parse workflow data from dict directly."""
        from addons.workflow_manager.workflow_parser import parse_workflow_from_dict

        models = parse_workflow_from_dict(sample_workflow_api_format)

        assert len(models) == 3

    def test_parse_empty_dict(self):
        """Should handle empty dict."""
        from addons.workflow_manager.workflow_parser import parse_workflow_from_dict

        result = parse_workflow_from_dict({})
        assert result == []

    def test_parse_dict_with_no_models(self):
        """Should handle dict with no model loader nodes."""
        from addons.workflow_manager.workflow_parser import parse_workflow_from_dict

        data = {
            "nodes": [
                {"id": 1, "class_type": "KSampler", "inputs": {}},
                {"id": 2, "class_type": "CLIPTextEncode", "inputs": {}},
            ]
        }

        result = parse_workflow_from_dict(data)
        assert result == []


class TestParsedModel:
    """Tests for ParsedModel dataclass."""

    def test_parsed_model_attributes(self):
        """ParsedModel should have all required attributes."""
        from addons.workflow_manager.workflow_parser import ParsedModel

        model = ParsedModel(
            filename="test.safetensors",
            node_type="UNETLoader",
            node_id="1",
            input_name="unet_name",
            target_path="diffusion_models",
        )

        assert model.filename == "test.safetensors"
        assert model.node_type == "UNETLoader"
        assert model.node_id == "1"
        assert model.input_name == "unet_name"
        assert model.target_path == "diffusion_models"


class TestModelLoaderNodes:
    """Tests for MODEL_LOADER_NODES constant."""

    def test_all_loaders_have_mapping(self):
        """All model loaders should have input_name and target_path."""
        from addons.workflow_manager.workflow_parser import MODEL_LOADER_NODES

        for node_type, (input_name, target_path) in MODEL_LOADER_NODES.items():
            assert isinstance(node_type, str)
            assert isinstance(input_name, str)
            assert isinstance(target_path, str)
            assert len(input_name) > 0
            assert len(target_path) > 0

    def test_common_loaders_exist(self):
        """Common model loaders should be defined."""
        from addons.workflow_manager.workflow_parser import MODEL_LOADER_NODES

        expected_loaders = [
            "UNETLoader",
            "VAELoader",
            "CheckpointLoaderSimple",
            "CLIPLoader",
            "LoraLoader",
            "ControlNetLoader",
        ]

        for loader in expected_loaders:
            assert loader in MODEL_LOADER_NODES, f"Missing loader: {loader}"

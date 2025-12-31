"""Parse ComfyUI workflow JSON files to extract model references."""

import json
from pathlib import Path
from typing import Dict, List, Set, Any, Optional
from dataclasses import dataclass


@dataclass
class ParsedModel:
    """A model reference found in a workflow."""
    filename: str
    node_type: str
    node_id: str
    input_name: str
    target_path: str  # Inferred from node type


# Node types that load models and their corresponding model paths
MODEL_LOADER_NODES = {
    # Diffusion models / UNETs
    "UNETLoader": ("unet_name", "diffusion_models"),
    "UnetLoaderGGUF": ("unet_name", "diffusion_models"),
    "WanI2VLoader": ("model", "diffusion_models/wan"),
    "DownloadAndLoadWanModel": ("model", "diffusion_models/wan"),

    # VAE
    "VAELoader": ("vae_name", "vae"),

    # Checkpoints (combined model + vae)
    "CheckpointLoaderSimple": ("ckpt_name", "checkpoints"),
    "CheckpointLoader": ("ckpt_name", "checkpoints"),

    # CLIP / Text Encoders
    "CLIPLoader": ("clip_name", "text_encoders"),
    "DualCLIPLoader": ("clip_name1", "text_encoders"),  # Also has clip_name2
    "CLIPVisionLoader": ("clip_name", "clip_vision"),
    "UNETLoaderNF4": ("unet_name", "diffusion_models"),

    # LoRA
    "LoraLoader": ("lora_name", "loras"),
    "LoraLoaderModelOnly": ("lora_name", "loras"),

    # ControlNet
    "ControlNetLoader": ("control_net_name", "controlnet"),

    # Upscale models
    "UpscaleModelLoader": ("model_name", "upscale_models"),

    # LLM / Vision models
    "DownloadAndLoadFlorence2Model": ("model", "LLM"),
    "Florence2ModelLoader": ("model_name", "LLM"),

    # LTX Video
    "LTXVLoader": ("ckpt_name", "checkpoints"),
}

# Additional inputs to check for secondary model references
SECONDARY_INPUTS = {
    "DualCLIPLoader": [("clip_name2", "text_encoders")],
    "LoraLoader": [("lora_name", "loras")],
}


def parse_workflow(workflow_path: Path) -> List[ParsedModel]:
    """Parse a ComfyUI workflow and extract all model references.

    Args:
        workflow_path: Path to the workflow JSON file

    Returns:
        List of ParsedModel objects found in the workflow
    """
    if not workflow_path.exists():
        return []

    try:
        with open(workflow_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"[Parser] Error loading workflow: {e}")
        return []

    models: List[ParsedModel] = []
    seen_filenames: Set[str] = set()

    # Handle both workflow formats
    # Format 1: {"nodes": [...], "links": [...]} (API format)
    # Format 2: {"1": {...}, "2": {...}} (node dict format)

    nodes = []

    if "nodes" in data:
        # API format
        nodes = data["nodes"]
    elif isinstance(data, dict):
        # Node dict format - check for numbered keys
        for key, value in data.items():
            if isinstance(value, dict) and "class_type" in value:
                value["_node_id"] = key
                nodes.append(value)

    for node in nodes:
        node_type = node.get("class_type", node.get("type", ""))
        node_id = str(node.get("_node_id", node.get("id", "?")))

        if node_type not in MODEL_LOADER_NODES:
            continue

        input_name, target_path = MODEL_LOADER_NODES[node_type]

        # Get inputs - can be in "inputs" or "widgets_values"
        inputs = node.get("inputs", {})
        widgets = node.get("widgets_values", [])

        # Try to find the model filename
        filename = None

        # Check inputs dict
        if isinstance(inputs, dict) and input_name in inputs:
            val = inputs[input_name]
            if isinstance(val, str):
                filename = val
            elif isinstance(val, list) and len(val) > 0:
                filename = str(val[0])

        # Check widgets_values (positional)
        if not filename and widgets:
            # First widget is usually the model name
            if len(widgets) > 0 and isinstance(widgets[0], str):
                filename = widgets[0]

        if filename and filename not in seen_filenames:
            seen_filenames.add(filename)
            models.append(ParsedModel(
                filename=filename,
                node_type=node_type,
                node_id=node_id,
                input_name=input_name,
                target_path=target_path,
            ))

        # Check secondary inputs
        if node_type in SECONDARY_INPUTS:
            for sec_input, sec_path in SECONDARY_INPUTS[node_type]:
                sec_filename = None

                if isinstance(inputs, dict) and sec_input in inputs:
                    val = inputs[sec_input]
                    if isinstance(val, str):
                        sec_filename = val

                if sec_filename and sec_filename not in seen_filenames:
                    seen_filenames.add(sec_filename)
                    models.append(ParsedModel(
                        filename=sec_filename,
                        node_type=node_type,
                        node_id=node_id,
                        input_name=sec_input,
                        target_path=sec_path,
                    ))

    return models


def parse_workflow_from_dict(data: Dict[str, Any]) -> List[ParsedModel]:
    """Parse workflow data already loaded as dict."""
    # Same logic as parse_workflow but takes dict directly
    models: List[ParsedModel] = []
    seen_filenames: Set[str] = set()

    nodes = []

    if "nodes" in data:
        nodes = data["nodes"]
    elif isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, dict) and "class_type" in value:
                value["_node_id"] = key
                nodes.append(value)

    for node in nodes:
        node_type = node.get("class_type", node.get("type", ""))
        node_id = str(node.get("_node_id", node.get("id", "?")))

        if node_type not in MODEL_LOADER_NODES:
            continue

        input_name, target_path = MODEL_LOADER_NODES[node_type]
        inputs = node.get("inputs", {})
        widgets = node.get("widgets_values", [])

        filename = None

        if isinstance(inputs, dict) and input_name in inputs:
            val = inputs[input_name]
            if isinstance(val, str):
                filename = val
            elif isinstance(val, list) and len(val) > 0:
                filename = str(val[0])

        if not filename and widgets:
            if len(widgets) > 0 and isinstance(widgets[0], str):
                filename = widgets[0]

        if filename and filename not in seen_filenames:
            seen_filenames.add(filename)
            models.append(ParsedModel(
                filename=filename,
                node_type=node_type,
                node_id=node_id,
                input_name=input_name,
                target_path=target_path,
            ))

    return models

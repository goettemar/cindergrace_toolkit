"""Known model URLs database for auto-suggestions."""

from dataclasses import dataclass


@dataclass
class KnownModel:
    """A known model with URL and metadata."""

    name: str
    filename: str
    url: str
    size_mb: int
    target_path: str
    aliases: list[str] = None  # Alternative filenames

    def __post_init__(self):
        if self.aliases is None:
            self.aliases = []


# Database of known models with HuggingFace URLs
KNOWN_MODELS: dict[str, KnownModel] = {
    # === WAN 2.2 Models ===
    "wan2.2_i2v_720p_14B_bf16.safetensors": KnownModel(
        name="WAN 2.2 14B I2V (bf16)",
        filename="wan2.2_i2v_720p_14B_bf16.safetensors",
        url="https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_repackaged/resolve/main/split_files/diffusion_models/wan2.2_i2v_720p_14B_bf16.safetensors",
        size_mb=28000,
        target_path="diffusion_models/wan",
    ),
    "wan2.2_i2v_720p_14B_fp8_e4m3fn.safetensors": KnownModel(
        name="WAN 2.2 14B I2V (fp8)",
        filename="wan2.2_i2v_720p_14B_fp8_e4m3fn.safetensors",
        url="https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_repackaged/resolve/main/split_files/diffusion_models/wan2.2_i2v_720p_14B_fp8_e4m3fn.safetensors",
        size_mb=14000,
        target_path="diffusion_models/wan",
    ),
    "wan2.2_i2v_720p_14B_bf16_HIGH.safetensors": KnownModel(
        name="WAN 2.2 14B HIGH Noise (bf16)",
        filename="wan2.2_i2v_720p_14B_bf16_HIGH.safetensors",
        url="https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_repackaged/resolve/main/split_files/diffusion_models/wan2.2_i2v_720p_14B_bf16_HIGH.safetensors",
        size_mb=25000,
        target_path="diffusion_models/wan",
    ),
    "wan2.2_i2v_720p_14B_bf16_LOW.safetensors": KnownModel(
        name="WAN 2.2 14B LOW Noise (bf16)",
        filename="wan2.2_i2v_720p_14B_bf16_LOW.safetensors",
        url="https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_repackaged/resolve/main/split_files/diffusion_models/wan2.2_i2v_720p_14B_bf16_LOW.safetensors",
        size_mb=25000,
        target_path="diffusion_models/wan",
    ),
    "wan2.2_i2v_480p_5B_bf16.safetensors": KnownModel(
        name="WAN 2.2 5B I2V (bf16)",
        filename="wan2.2_i2v_480p_5B_bf16.safetensors",
        url="https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_repackaged/resolve/main/split_files/diffusion_models/wan2.2_i2v_480p_5B_bf16.safetensors",
        size_mb=10000,
        target_path="diffusion_models/wan",
    ),
    "wan_2.2_vae.safetensors": KnownModel(
        name="WAN 2.2 VAE",
        filename="wan_2.2_vae.safetensors",
        url="https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_repackaged/resolve/main/split_files/vae/wan_2.2_vae.safetensors",
        size_mb=250,
        target_path="vae",
    ),
    "umt5_xxl_encoder_q4_k_m.gguf": KnownModel(
        name="UMT5-XXL Encoder (GGUF)",
        filename="umt5_xxl_encoder_q4_k_m.gguf",
        url="https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_encoder_q4_k_m.gguf",
        size_mb=5000,
        target_path="text_encoders",
    ),
    "clip_vision_h.safetensors": KnownModel(
        name="CLIP Vision H",
        filename="clip_vision_h.safetensors",
        url="https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_repackaged/resolve/main/split_files/clip_vision/clip_vision_h.safetensors",
        size_mb=3500,
        target_path="clip_vision",
    ),
    # === WAN LoRAs ===
    "svi.safetensors": KnownModel(
        name="SVI LoRA",
        filename="svi.safetensors",
        url="https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/svi.safetensors",
        size_mb=800,
        target_path="loras/wan",
    ),
    "wan_lighting_lora.safetensors": KnownModel(
        name="WAN Lightning LoRA",
        filename="wan_lighting_lora.safetensors",
        url="https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/wan_lighting_lora.safetensors",
        size_mb=400,
        target_path="loras/wan",
    ),
    # === FLUX Models ===
    "flux1-dev.safetensors": KnownModel(
        name="FLUX.1 Dev",
        filename="flux1-dev.safetensors",
        url="https://huggingface.co/black-forest-labs/FLUX.1-dev/resolve/main/flux1-dev.safetensors",
        size_mb=24000,
        target_path="diffusion_models",
    ),
    "flux1-dev-fp8.safetensors": KnownModel(
        name="FLUX.1 Dev (fp8)",
        filename="flux1-dev-fp8.safetensors",
        url="https://huggingface.co/Comfy-Org/flux1-dev/resolve/main/flux1-dev-fp8.safetensors",
        size_mb=12000,
        target_path="diffusion_models",
    ),
    "ae.safetensors": KnownModel(
        name="FLUX VAE (ae)",
        filename="ae.safetensors",
        url="https://huggingface.co/black-forest-labs/FLUX.1-dev/resolve/main/ae.safetensors",
        size_mb=300,
        target_path="vae",
    ),
    "t5xxl_fp16.safetensors": KnownModel(
        name="T5-XXL (fp16)",
        filename="t5xxl_fp16.safetensors",
        url="https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp16.safetensors",
        size_mb=9500,
        target_path="text_encoders",
    ),
    "t5xxl_fp8_e4m3fn.safetensors": KnownModel(
        name="T5-XXL (fp8)",
        filename="t5xxl_fp8_e4m3fn.safetensors",
        url="https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp8_e4m3fn.safetensors",
        size_mb=4700,
        target_path="text_encoders",
    ),
    "clip_l.safetensors": KnownModel(
        name="CLIP-L",
        filename="clip_l.safetensors",
        url="https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors",
        size_mb=250,
        target_path="text_encoders",
    ),
    # === SDXL Models ===
    "sd_xl_base_1.0.safetensors": KnownModel(
        name="SDXL Base 1.0",
        filename="sd_xl_base_1.0.safetensors",
        url="https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors",
        size_mb=6900,
        target_path="checkpoints",
    ),
    "sdxl_vae.safetensors": KnownModel(
        name="SDXL VAE",
        filename="sdxl_vae.safetensors",
        url="https://huggingface.co/stabilityai/sdxl-vae/resolve/main/sdxl_vae.safetensors",
        size_mb=350,
        target_path="vae",
    ),
    # === LTX Video ===
    "ltx-video-2b-v0.9.safetensors": KnownModel(
        name="LTX Video 2B",
        filename="ltx-video-2b-v0.9.safetensors",
        url="https://huggingface.co/Lightricks/LTX-Video/resolve/main/ltx-video-2b-v0.9.safetensors",
        size_mb=9000,
        target_path="checkpoints",
    ),
    # === Florence2 ===
    "Florence-2-large": KnownModel(
        name="Florence 2 Large",
        filename="Florence-2-large",
        url="https://huggingface.co/microsoft/Florence-2-large",
        size_mb=1500,
        target_path="LLM",
    ),
}


def suggest_url(filename: str) -> KnownModel | None:
    """Look up a filename and return known model info if available."""
    # Direct match
    if filename in KNOWN_MODELS:
        return KNOWN_MODELS[filename]

    # Try lowercase
    filename_lower = filename.lower()
    for key, model in KNOWN_MODELS.items():
        if key.lower() == filename_lower:
            return model

    # Check aliases
    for key, model in KNOWN_MODELS.items():
        if filename in model.aliases or filename_lower in [a.lower() for a in model.aliases]:
            return model

    return None


def get_all_known_models() -> list[KnownModel]:
    """Get all known models."""
    return list(KNOWN_MODELS.values())

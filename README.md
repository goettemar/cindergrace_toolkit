# Cindergrace Toolkit

Modulares Gradio-Toolkit für ComfyUI - Workflow-basierte Modellverwaltung mit VRAM-Tiers.

## Features

### Model Depot
- Workflow-basierte Modellverwaltung mit VRAM-Tiers (S/M/L)
- Automatischer Download fehlender Modelle
- Restore aus Backup-Verzeichnis
- "Andere Modelle löschen" - Platz schaffen durch Entfernen nicht benötigter Modelle
- Disk-Space Anzeige beim Start (wichtig für RunPod!)

### Workflow Manager (nur lokal)
- Workflows aus ComfyUI parsen und Model-Definitionen erstellen
- VRAM-Tier Zuordnung (S=8-12GB, M=16GB, L=24-32GB)
- Zielordner verwalten
- Speichert direkt in `data/workflow_models.json`

### System Info
- GPU, VRAM, RAM Anzeige
- Umgebungserkennung (local/runpod/colab)

## Architektur

```
cindergrace_toolkit/
├── app.py                      # Hauptanwendung
├── core/
│   ├── addon_loader.py         # Dynamisches Addon-Loading
│   ├── base_addon.py           # Addon-Basisklasse
│   └── config_manager.py       # Konfigurationsverwaltung
├── addons/
│   ├── model_depot/            # Model Download & Management
│   ├── workflow_manager/       # Workflow-Definition Editor
│   └── system_info/            # System-Informationen
├── config/
│   ├── releases/               # Release-Konfigurationen
│   │   ├── full.json           # Lokal: alle Addons
│   │   ├── runpod.json         # RunPod: ohne Workflow Manager
│   │   └── minimal.json        # Minimal: nur Model Depot
│   └── config.json             # Standard-Konfiguration
├── .config/
│   └── config.json             # User-Konfiguration (optional, .gitignore)
└── data/
    └── workflow_models.json    # Workflow & Model Definitionen (Git)
```

## Konfiguration

### Pfade (`config/config.json` oder `.config/config.json`)

```json
{
  "paths": {
    "comfyui": {
      "local": "~/ComfyUI",
      "runpod": "/workspace/ComfyUI",
      "colab": "/content/ComfyUI"
    },
    "workflows": {
      "local": "{comfyui}/user/default/workflows",
      "runpod": "{comfyui}/user/default/workflows"
    },
    "backup": {
      "local": "",
      "runpod": "/runpod-volume/models_backup"
    }
  },
  "workflow_pattern": "gc*.json"
}
```

### Workflow Models (`data/workflow_models.json`)

Dies ist die **einzige Quelle** für Workflow- und Model-Definitionen. Wird via Git synchronisiert.

```json
{
  "version": "1.1.0",
  "target_folders": ["checkpoints", "diffusion_models", "vae", "loras", "text_encoders"],
  "workflows": {
    "gcv_wan_2.2_14b_i2v": {
      "name": "WAN 2.2 14B I2V",
      "category": "video",
      "model_sets": {
        "24GB": {
          "name": "24GB VRAM",
          "vram_gb": 24,
          "models": ["wan22_14b_bf16", "wan22_vae", "wan22_clip"]
        },
        "16GB": {
          "name": "16GB VRAM",
          "vram_gb": 16,
          "models": ["wan22_14b_fp8", "wan22_vae", "wan22_clip"]
        }
      }
    }
  },
  "models": {
    "wan22_14b_bf16": {
      "filename": "wan2.2_i2v_720p_14B_bf16.safetensors",
      "url": "https://huggingface.co/...",
      "size_mb": 28000,
      "target_path": "diffusion_models/wan"
    }
  }
}
```

## Installation

```bash
git clone https://github.com/cindergrace/cindergrace_toolkit.git
cd cindergrace_toolkit
pip install -r requirements.txt
```

## Verwendung

### Lokal

```bash
# Auto-Detect (lädt 'full' Release)
python app.py

# Mit spezifischem Port
python app.py --port 7862
```

### RunPod / Colab

```bash
# Automatische Erkennung (lädt 'runpod' Release)
python app.py

# Workflow Manager ist deaktiviert (read-only Umgebung)
```

### Kommandozeilen-Optionen

| Option | Beschreibung |
|--------|--------------|
| `--release`, `-r` | Release-Konfiguration (full, runpod, minimal) |
| `--port`, `-p` | Server-Port (default: 7861) |
| `--share` | Öffentlichen Gradio-Link erstellen |
| `--profile-url` | URL für Remote Profiles |

## Release-Konfigurationen

| Release | Addons | Plattform |
|---------|--------|-----------|
| `full` | Model Depot, Workflow Manager, System Info | Lokal |
| `runpod` | Model Depot, System Info | RunPod/Colab |
| `minimal` | Model Depot | Überall |

## VRAM-Tiers

| Tier | VRAM | Typische Modelle |
|------|------|------------------|
| S | 8-12 GB | SDXL, WAN 5B |
| M | 16 GB | FP8 quantisiert |
| L | 24-32 GB | BF16 Full Quality |

## Workflow

### Lokale Entwicklung

1. **Workflow Manager** öffnen
2. Workflow aus ComfyUI auswählen
3. "Auto-Parse" um Modelle zu erkennen
4. VRAM-Tiers zuordnen (S/M/L Checkboxen)
5. URLs und Ordner anpassen
6. "Speichern" (schreibt nach `data/workflow_models.json`)
7. `git commit && git push`

### RunPod Deployment

1. `git pull` (holt aktuelle `data/workflow_models.json`)
2. App starten (`python app.py`)
3. Model Depot zeigt verfügbare Workflows
4. VRAM-Tier passend zur GPU wählen
5. Fehlende Modelle downloaden

## Eigene Addons erstellen

```python
# addons/mein_addon/addon.py
from core.base_addon import BaseAddon
import gradio as gr

class MeinAddon(BaseAddon):
    def __init__(self):
        super().__init__()
        self.name = "Mein Addon"
        self.icon = "🚀"
        self.version = "1.0.0"

    def get_tab_name(self) -> str:
        return f"{self.icon} {self.name}"

    def on_load(self) -> None:
        # Initialisierung beim App-Start
        pass

    def render(self) -> gr.Blocks:
        with gr.Blocks() as ui:
            gr.Markdown(f"## {self.icon} {self.name}")
            # UI hier...
        return ui
```

Addon in Release aktivieren (`config/releases/full.json`):

```json
{
  "addons": [
    {"id": "mein_addon", "enabled": true}
  ]
}
```

## Disk-Space Warnings

The toolkit shows storage information at startup:

- OK: >50 GB free
- Low: <50 GB free
- Warning: <10 GB free or >90% used

Especially important on RunPod to recognize whether `/workspace` (temporary, small) or `/runpod-volume` (persistent, large) is being used.

## Security

### SSL Verification

SSL certificate verification is **enabled by default**. If you encounter SSL errors (e.g., with corporate proxies or self-signed certificates), you can disable verification:

```json
// config/config.json or .config/config.json
{
  "security": {
    "disable_ssl_verify": true
  }
}
```

**Warning:** Disabling SSL verification exposes you to man-in-the-middle attacks. Only use this option if absolutely necessary and you understand the risks.

### Path Traversal Protection

The toolkit validates all file paths to prevent directory traversal attacks. Only whitelisted target folders are allowed:
- `checkpoints`, `diffusion_models`, `vae`, `loras`, `text_encoders`, `clip_vision`, `controlnet`, `upscale_models`, `LLM`

## Roadmap

### Next Release
- [ ] Remote Profiles via Git URL
- [ ] HuggingFace Token Integration
- [ ] Download queue with progress bar
- [ ] Model verification (SHA256)

### Future Releases
- [ ] Per-model download/restore actions in table
- [ ] Download resume & cancel support
- [ ] Parallel download limit (configurable)
- [ ] Config UI (edit paths, VRAM tiers in app)
- [ ] Status aggregates (total MB to download/free)
- [ ] Scan caching for large model collections
- [ ] Harden target folder validation (reject `..`/backslashes, normalize paths)
- [ ] Add regression tests for disclaimer flow and path sanitization

## License

CC BY-NC 4.0 (Creative Commons Attribution-NonCommercial 4.0 International)

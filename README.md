# Cindergrace Toolkit

Modulares Gradio-Toolkit für ComfyUI - Workflow-basierte Modellverwaltung, Custom Nodes und Workflow-Sync.

## Features

### Model Depot
- Workflow-basierte Modellverwaltung mit VRAM-Tiers (S/M/L)
- Automatischer Download fehlender Modelle
- Restore aus Backup-Verzeichnis
- "Andere Modelle löschen" - Platz schaffen durch Entfernen nicht benötigter Modelle
- Disk-Space Anzeige beim Start (wichtig für RunPod!)

### Custom Nodes Manager (NEU)
- Custom Nodes aus `data/custom_nodes.json` verwalten
- Enable/Disable Nodes ohne Image-Rebuild
- Sync-Script für automatische Installation bei Pod-Start
- Nodes hinzufügen/entfernen über UI

### Workflow Manager (nur lokal)
- Workflows aus ComfyUI parsen und Model-Definitionen erstellen
- VRAM-Tier Zuordnung (S=8-12GB, M=16GB, L=24-32GB)
- Zielordner verwalten
- Speichert direkt in `data/workflow_models.json`

### Workflow Sync (NEU)
- Workflows in `data/workflows/` zentral verwalten
- Automatischer Sync zu ComfyUI bei Pod-Start
- Kein manuelles Kopieren mehr nötig

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
│   ├── custom_nodes_manager/   # Custom Nodes Management (NEU)
│   ├── workflow_manager/       # Workflow-Definition Editor
│   └── system_info/            # System-Informationen
├── scripts/
│   ├── sync_nodes.py           # Custom Nodes Sync Script (NEU)
│   └── sync_workflows.py       # Workflow Sync Script (NEU)
├── config/
│   ├── releases/               # Release-Konfigurationen
│   │   ├── full.json           # Lokal: alle Addons
│   │   ├── runpod.json         # RunPod: mit Custom Nodes Manager
│   │   └── minimal.json        # Minimal: nur Model Depot
│   └── config.json             # Standard-Konfiguration
├── .config/
│   └── config.json             # User-Konfiguration (optional, .gitignore)
└── data/
    ├── workflow_models.json    # Workflow & Model Definitionen (Git)
    ├── custom_nodes.json       # Custom Nodes Definitionen (NEU)
    └── workflows/              # Workflow JSON Dateien (NEU)
        └── *.json
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

### Custom Nodes (`data/custom_nodes.json`)

Definiert welche Custom Nodes installiert werden sollen:

```json
{
  "version": "1.0.0",
  "nodes": [
    {
      "id": "comfyui-manager",
      "name": "ComfyUI Manager",
      "url": "https://github.com/ltdrdata/ComfyUI-Manager.git",
      "description": "Essential node manager",
      "enabled": true,
      "required": true
    },
    {
      "id": "comfyui-wanvideowrapper",
      "name": "WAN Video Wrapper",
      "url": "https://github.com/kijai/ComfyUI-WanVideoWrapper.git",
      "enabled": true
    }
  ]
}
```

### Workflows (`data/workflows/`)

Workflow JSON-Dateien hier ablegen. Diese werden automatisch nach `ComfyUI/user/default/workflows/` synchronisiert.

### Workflow Models (`data/workflow_models.json`)

Definiert Modelle für Workflows:

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

### Sync Scripts (CLI)

```bash
# Custom Nodes synchronisieren
python scripts/sync_nodes.py --comfyui-path /workspace/ComfyUI

# Workflows synchronisieren
python scripts/sync_workflows.py --comfyui-path /workspace/ComfyUI

# Dry-run (zeigt was passieren würde)
python scripts/sync_nodes.py --dry-run
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
| `full` | Model Depot, Custom Nodes Manager, Workflow Manager, System Info | Lokal |
| `runpod` | Model Depot, Custom Nodes Manager, System Info | RunPod/Colab |
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
7. Workflow JSON nach `data/workflows/` kopieren
8. `git commit && git push`

### RunPod Deployment

1. Pod startet → Toolkit wird geklont/aktualisiert
2. Custom Nodes werden automatisch installiert
3. Workflows werden automatisch synchronisiert
4. Model Depot zeigt verfügbare Workflows
5. VRAM-Tier passend zur GPU wählen
6. Fehlende Modelle downloaden

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
- [x] Custom Nodes Manager
- [x] Workflow Sync
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

## License

CC BY-NC 4.0 (Creative Commons Attribution-NonCommercial 4.0 International)

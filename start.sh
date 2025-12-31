#!/bin/bash
# Cindergrace Toolkit Starter
# - Auto-Update von GitHub
# - Erstellt venv bei Bedarf
# - Startet die Anwendung

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR=".venv"
PYTHON="python3"
NO_UPDATE=false

# Farben für Output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Argumente parsen
for arg in "$@"; do
    case $arg in
        --no-update)
            NO_UPDATE=true
            shift
            ;;
    esac
done

echo -e "${GREEN}🔧 Cindergrace Toolkit${NC}"
echo "========================"

# === Auto-Update ===
if [ "$NO_UPDATE" = false ] && [ -d ".git" ]; then
    echo -e "${BLUE}🔄 Prüfe auf Updates...${NC}"

    # Fetch remote
    if git fetch origin main --quiet 2>/dev/null; then
        # Check if behind
        LOCAL=$(git rev-parse HEAD 2>/dev/null)
        REMOTE=$(git rev-parse origin/main 2>/dev/null)

        if [ "$LOCAL" != "$REMOTE" ]; then
            BEHIND=$(git rev-list --count HEAD..origin/main 2>/dev/null || echo "0")
            echo -e "${YELLOW}📥 $BEHIND neue Commits verfügbar${NC}"

            # Show changes
            echo -e "${BLUE}Änderungen:${NC}"
            git log --oneline HEAD..origin/main | head -5

            # Pull updates
            echo -e "${YELLOW}⬇️ Lade Updates...${NC}"
            if git pull origin main --quiet 2>/dev/null; then
                echo -e "${GREEN}✅ Update erfolgreich!${NC}"

                # Check if requirements changed
                if git diff HEAD~$BEHIND --name-only | grep -q "requirements.txt"; then
                    echo -e "${YELLOW}📦 Requirements haben sich geändert, installiere neu...${NC}"
                    rm -rf "$VENV_DIR"
                fi
            else
                echo -e "${RED}⚠️ Update fehlgeschlagen, fahre mit aktueller Version fort${NC}"
            fi
        else
            echo -e "${GREEN}✅ Bereits aktuell${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️ Keine Verbindung zum Repository${NC}"
    fi
    echo ""
fi

# === Python prüfen ===
if ! command -v $PYTHON &> /dev/null; then
    echo -e "${RED}❌ Python3 nicht gefunden!${NC}"
    exit 1
fi

# === venv erstellen falls nicht vorhanden ===
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}📦 Erstelle virtuelle Umgebung...${NC}"
    $PYTHON -m venv "$VENV_DIR"
    echo "✅ venv erstellt"
fi

# === venv aktivieren ===
source "$VENV_DIR/bin/activate"

# === Requirements prüfen und installieren ===
if [ -f "requirements.txt" ]; then
    if ! $PYTHON -c "import gradio" 2>/dev/null; then
        echo -e "${YELLOW}📥 Installiere Requirements...${NC}"
        pip install --upgrade pip -q
        pip install -r requirements.txt
        echo "✅ Requirements installiert"
    fi
fi

# === Starten ===
echo ""
echo -e "${GREEN}🚀 Starte Toolkit...${NC}"
echo ""

# Argumente durchreichen (ohne --no-update)
$PYTHON app.py "$@"

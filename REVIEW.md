# Review: Cindergrace Toolkit

## Findings (Schwachstellen & Risiken)

- **High**: TLS/SSL-Validierung ist deaktiviert bei Remote-Configs, Profile-Downloads und Model-Downloads, wodurch MITM-Angriffe möglich sind (z.B. manipulierte Releases/Profiles/Modelle). Betroffen: `core/addon_loader.py:68`, `core/profile_sync.py:43`, `addons/model_depot/addon.py:328`.
- **High**: Pfad-Traversal ist möglich, weil `target_path`/`filename` ungeprüft verwendet werden. Ein manipuliertes `workflow_models.json` oder ein bösartiger Client-Request könnte Downloads/Deletes außerhalb von `models`/`backup` ausführen. Betroffen: `addons/model_depot/addon.py:314`, `addons/model_depot/addon.py:445`, `addons/workflow_manager/addon.py:245`.
- **Medium**: Fallback-Logik für fehlende Releases lädt zwar `minimal`, versucht aber danach weiterhin das nicht vorhandene Release zu laden und kann die App abbrechen. Betroffen: `app.py:103`, `app.py:112`.
- **Medium**: `model_id` wird aus dem Dateinamen generiert und kann kollidieren (z.B. unterschiedliche Dateien, die nach Normalisierung gleich werden). Das überschreibt Modell-Einträge still und verändert Workflows. Betroffen: `addons/workflow_manager/addon.py:255`.
- **Low**: Auto-Update im Startskript macht `git pull` ohne Dirty-Check/Backup, was bei lokalen Änderungen zu unerwarteten Konflikten führen kann. Betroffen: `start.sh:56`.

## Optimierungsmöglichkeiten (Performance & Robustheit)

- Download-Threads sind unlimitiert (ein Thread pro Model). `download_parallel` aus `config/settings.json` wird nicht genutzt; eine Queue mit Worker-Limit würde RAM/IO-Spikes vermeiden und stabiler skalieren.
- `find_other_models` iteriert per `Path.iterdir()` ohne `os.scandir` und jedes Refresh rescant alle Ordner; bei großen Model-Pools kann das spürbar träge werden. Ein Cache oder On-Demand-Scan mit Progress wäre hilfreicher.
- `_load_workflow_models()` wird bei jedem UI-Event neu geladen. Das ist sicher, aber redundant. Ein einfacher Änderungs-Timestamp/Hash würde I/O reduzieren.
- `download_model` prüft keine erwartete Dateigröße/Checksum (liegt in JSON), wodurch beschädigte oder unvollständige Downloads unbemerkt bleiben.
- UI-Theme-Konfiguration existiert (`config/config.json`), wird aber in `app.py` ignoriert; konsistente Nutzung würde Support reduzieren.

## Bedienbarkeit & Aufwertungsideen

- **Per-Model Actions**: In der Model-Tabelle fehlt ein direkter "Download/Restore" pro Zeile. Das reduziert Kontrolle, gerade bei großen Model-Sets.
- **Integritäts-Check**: SHA256-Verifikation + Hinweis bei Mismatch (z.B. gelbe Warnung statt nur "present").
- **Konfig-UI**: Pfade, Remote-Profiles und VRAM-Tiers im UI editierbar machen; aktuell ist `config.json`/`.config/config.json` manuell.
- **Sicherheits-Guardrails**: `target_path`/`filename` normalisieren, `..`/absolute Pfade sperren und nur whitelisted Ordner erlauben.
- **Download-Resume & Cancel**: Resume-Support (HTTP range) und Abbruch-Knopf pro Download verbessert UX und spart Zeit.
- **Status-Aggregate**: "Platz sparen" Anzeige (Summe MB) und "Fehlende Models insgesamt" als Dashboard-Karte.

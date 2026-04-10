# drone2map

**Drohnenbilder zu Orthofoto, DSM und DGM verarbeiten** – eine Python-Desktop-Anwendung auf Basis von [OpenDroneMap (ODM)](https://www.opendronemap.org/).

![Hauptfenster](docs/screenshots/main_window.png) <!-- Screenshot-Platzhalter -->

## Funktionen

- 📁 Drohnenbilder importieren (JPEG, TIFF, PNG) – einzeln oder als Ordner
- 🗺️ GPS-Koordinaten aus EXIF-Metadaten extrahieren und auf interaktiver Karte anzeigen
- ⚙️ Verarbeitung über NodeODM REST-API oder lokale ODM CLI (automatischer Fallback)
- 🔁 Robuste Fehlerbehandlung mit konfigurierbarer Wiederholungslogik
- 📊 Ergebnisse: Orthofoto, DSM (Digitales Oberflächenmodell), DTM (Digitales Geländemodell), Punktwolke
- 💾 Export als GeoTIFF, optional mit Reprojektion in das optimale UTM-Koordinatensystem
- 🗂️ Projektmanagement: Projekte als JSON speichern, laden, zuletzt verwendete Projekte

## Screenshots

| Hauptfenster | Einstellungen |
|---|---|
| ![Hauptfenster](docs/screenshots/main_window.png) | ![Einstellungen](docs/screenshots/settings.png) |

*Screenshots werden nach dem ersten Start automatisch aktualisiert.*

## Installation

### Voraussetzungen

- Python 3.10 oder höher
- [NodeODM](https://github.com/OpenDroneMap/NodeODM) (empfohlen) **oder** ODM CLI

### Python-Paket

```bash
pip install -r requirements.txt
pip install -e .
```

### NodeODM via Docker (empfohlen)

```bash
docker run -ti -p 3000:3000 opendronemap/nodeodm
```

Danach in den Einstellungen Host `localhost`, Port `3000` eintragen.

## Schnellstart

1. **Anwendung starten**
   ```bash
   drone2map
   # oder
   python -m drone2map.main
   ```

2. **Projekt anlegen**: Datei → Neues Projekt, Ausgabeverzeichnis wählen

3. **Bilder hinzufügen**: Schaltfläche „+ Bilder" oder „Ordner" in der Toolbar (mind. 3 Bilder mit GPS-EXIF)

4. **NodeODM prüfen**: Einstellungen → NodeODM → „Verbindung testen"

5. **Verarbeitung starten**: Schaltfläche „▶ Starten" im Fortschritts-Panel

6. **Ergebnisse**: Werden im gewählten Ausgabeverzeichnis abgelegt (Orthofoto, DSM, DTM, Punktwolke)

## CLI-Flags

```bash
drone2map --project /pfad/zum/projekt.d2m.json   # Projekt direkt öffnen
drone2map --version                               # Version anzeigen
```

## Architektur

```
drone2map/
├── main.py                  # Entry-Point (CLI-Flags, AppSettings laden, App starten)
├── gui/
│   ├── app.py               # Haupt-tkinter/ttkbootstrap Fenster, Event-Polling
│   ├── styles.py            # Theme-Konfiguration, Tile-Server-Definitionen
│   └── widgets/
│       ├── image_list.py    # Bildlisten-Widget mit Thumbnails, Delete-Taste
│       ├── map_view.py      # Kartenanzeige (tkintermapview), Tile-Server-Umschalter
│       ├── metadata_panel.py # EXIF-Metadaten-Anzeige des ausgewählten Bildes
│       ├── progress_panel.py # Fortschrittsbalken + Log-Textfeld + Start/Stop
│       └── settings_dialog.py # Modaler Einstellungsdialog (ODM-Parameter, Retry)
├── core/
│   ├── exif_parser.py       # EXIF/GPS-Extraktion (exifread + Pillow-Fallback)
│   ├── geo_utils.py         # WGS84↔UTM, Haversine, BBox, GSD-Berechnung
│   ├── project.py           # Projektmodell (JSON), Einstellungen-Dataclass
│   └── validators.py        # Bildvalidierung (Format, GPS, Dateigröße)
├── processing/
│   ├── odm_runner.py        # NodeODM REST-API (pyodm) + ODM CLI Fallback, Retry
│   ├── pipeline.py          # Orchestrierung, Queue-Events, Pipeline.retry()
│   └── export.py            # GeoTIFF-Export, Reprojektion (rasterio), Bericht
└── config/
    └── settings.py          # App-weite Einstellungen (JSON, ~/.drone2map/)
```

### Datenfluss

```
Bilder (JPEG/TIFF/PNG)
    │
    ▼
ExifParser          → GPS, Kamera, Datum, Brennweite …
    │
    ▼
ImageValidator      → Format, GPS vorhanden?, Dateigröße OK?
    │
    ▼
OdmRunner           → NodeODM REST-API  (Retry bei Verbindungsabbruch)
  (Fallback)        → ODM CLI (subprocess)
    │
    ▼
Exporter            → GeoTIFF kopieren / reprojizieren, Exportbericht
    │
    ▼
Ergebnisse:  orthophoto.tif · dsm.tif · dtm.tif · pointcloud.laz
```

Events fließen über eine `queue.Queue` vom Hintergrund-Thread zur GUI (`ProgressEvent`, `MetadataEvent`, `DoneEvent`, `ErrorEvent`).

## Einstellungen

| Parameter | Beschreibung | Standard |
|-----------|-------------|---------|
| DSM erzeugen | Digitales Oberflächenmodell | ✓ |
| DTM erzeugen | Digitales Geländemodell | ✓ |
| Orthofoto-Auflösung | GSD in cm/Pixel | 5 |
| Feature-Qualität | `lowest` / `low` / `medium` / `high` / `ultra` | `high` |
| PC-Qualität | Punktwolken-Qualität | `high` |
| Mesh-Octree-Tiefe | ODM mesh-octree-depth | 12 |
| NodeODM Host | Hostname des NodeODM-Servers | `localhost` |
| NodeODM Port | Port des NodeODM-Servers | `3000` |
| Max. Wiederholungen | Anzahl Retry-Versuche bei Verbindungsabbruch | `3` |
| Wartezeit zw. Versuchen | Pause in Sekunden zwischen Retry-Versuchen | `5.0` |

Einstellungen werden in `~/.drone2map/settings.json` gespeichert.

## Abhängigkeiten

| Paket | Zweck |
|-------|-------|
| `ttkbootstrap` | Modernes tkinter-Theme (darkly/cosmo) |
| `tkintermapview` | OpenStreetMap-Kartenansicht |
| `exifread` | EXIF-Metadaten-Extraktion |
| `Pillow` | Bild-Fallback, Thumbnails |
| `pyodm` | NodeODM REST-API Client |
| `pyproj` | WGS84↔UTM Koordinatentransformation |
| `rasterio` | GeoTIFF-Export und Reprojektion |
| `numpy` | Geo-Berechnungen |
| `pytest` | Unit-Tests (dev) |

## Tests

```bash
cd drone2map
pip install pytest
python -m pytest tests/ -q
```

Aktuelle Testabdeckung: **106 Tests** in 8 Modulen (`test_exif_parser`, `test_geo_utils`, `test_project`, `test_validators`, `test_export`, `test_pipeline`, `test_settings`, `test_odm_runner`).

## Lizenz

MIT – siehe [LICENSE](LICENSE)

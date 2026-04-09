# drone2map

**Drohnenbilder zu Orthofoto, DSM und DGM verarbeiten** – eine Python-Desktop-Anwendung auf Basis von [OpenDroneMap (ODM)](https://www.opendronemap.org/).

## Funktionen

- Drohnenbilder importieren (JPEG, TIFF, PNG)
- GPS-Koordinaten aus EXIF-Metadaten extrahieren und auf Karte anzeigen
- Verarbeitung über NodeODM REST-API oder ODM CLI
- Ergebnisse: Orthofoto, DSM, DTM, Punktwolke
- Export in GeoTIFF, optional mit Reprojektion

## Installation

```bash
pip install -r requirements.txt
pip install -e .
```

## Starten

```bash
drone2map
# oder
python -m drone2map.main
```

## Voraussetzungen

- Python 3.10+
- [NodeODM](https://github.com/OpenDroneMap/NodeODM) läuft lokal auf Port 3000 (Standard)
- Mindestens 3 Bilder mit GPS-EXIF-Daten

## Projektstruktur

```
drone2map/
├── config/       Einstellungen (JSON)
├── core/         EXIF-Parser, Geo-Berechnungen, Projektmodell
├── processing/   ODM-Runner, Pipeline, Export
└── gui/          ttkbootstrap GUI, Widgets
tests/            pytest-Einheitstests
```

## Tests

```bash
pytest tests/
```

## Lizenz

MIT

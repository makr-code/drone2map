# drone2map – Benutzerhandbuch

## Schnellstart

1. **Anwendung starten**: `drone2map` oder `python -m drone2map.main`
2. **Bilder hinzufügen**: Schaltfläche „+ Bilder" oder „Ordner" in der Toolbar
3. **Einstellungen prüfen**: Menü → Einstellungen (NodeODM-Host, Ausgabeverzeichnis, ODM-Parameter)
4. **Verarbeitung starten**: Schaltfläche „▶ Starten" im Fortschritts-Panel
5. **Ergebnisse**: Werden im gewählten Ausgabeverzeichnis abgelegt

## Bilder laden

- Unterstützte Formate: JPEG, TIFF, PNG
- Bilder benötigen GPS-EXIF-Daten (Latitude, Longitude)
- Mindestens 3 Bilder für die Verarbeitung erforderlich
- Die Karte zeigt alle Bildpositionen an

## Einstellungen

| Parameter | Beschreibung |
|-----------|-------------|
| Ausgabeverzeichnis | Zielordner für Ergebnisdateien |
| DSM erzeugen | Digitales Oberflächenmodell |
| DTM erzeugen | Digitales Geländemodell |
| Orthofoto-Auflösung | GSD in cm/Pixel |
| Feature-Qualität | lowest / low / medium / high / ultra |
| PC-Qualität | Punktwolken-Qualität |
| NodeODM Host/Port | Adresse des NodeODM-Servers |
| Max. Wiederholungen | Retry-Versuche bei Verbindungsabbruch (Standard: 3) |
| Wartezeit zw. Versuchen | Pause in Sekunden zwischen Retries (Standard: 5 s) |

## Projekte

- **Neu**: Datei → Neues Projekt
- **Speichern**: Datei → Projekt speichern (*.d2m.json)
- **Laden**: Datei → Projekt öffnen

## Ergebnisdateien

| Datei | Beschreibung |
|-------|-------------|
| orthophoto.tif | Georeferenziertes Orthofoto |
| dsm.tif | Digitales Oberflächenmodell |
| dtm.tif | Digitales Geländemodell |
| pointcloud.laz | Georeferenzierte Punktwolke |

## NodeODM einrichten

```bash
# Docker
docker run -p 3000:3000 opendronemap/nodeodm
```

Danach in den Einstellungen Host `localhost`, Port `3000` eintragen.

"""Einstiegspunkt der drone2map Anwendung."""
from __future__ import annotations
import argparse
import logging
import sys


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _parse_args() -> argparse.Namespace:
    from . import __version__
    parser = argparse.ArgumentParser(
        prog="drone2map",
        description="Drohnenbilder zu Orthofoto, DSM und DGM (OpenDroneMap).",
    )
    parser.add_argument("--version", action="version", version=f"drone2map {__version__}")
    parser.add_argument(
        "--project",
        metavar="FILE",
        help="Projektdatei (.d2m.json) beim Start direkt öffnen",
    )
    return parser.parse_args()


def main() -> None:
    _setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("drone2map wird gestartet…")

    args = _parse_args()

    try:
        from .config.settings import AppSettings
        settings = AppSettings.load()
    except Exception as exc:
        logger.warning("Einstellungen nicht geladen: %s", exc)
        from .config.settings import AppSettings
        settings = AppSettings()

    try:
        from .gui.app import App
        app = App(settings)
        if args.project:
            app.open_project_file(args.project)
        app.run()
    except Exception as exc:
        logger.exception("Unbehandelter Fehler: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()

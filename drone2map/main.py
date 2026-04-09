"""Einstiegspunkt der drone2map Anwendung."""
from __future__ import annotations
import logging
import sys


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def main() -> None:
    _setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("drone2map wird gestartet…")

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
        app.run()
    except Exception as exc:
        logger.exception("Unbehandelter Fehler: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()

"""Tests für drone2map.processing.pipeline."""
from __future__ import annotations
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from drone2map.core.project import Project, ProjectSettings
from drone2map.processing.pipeline import (
    Pipeline,
    ProgressEvent,
    MetadataEvent,
    DoneEvent,
    ErrorEvent,
)


def _make_project(tmp_path, image_count: int = 3) -> Project:
    proj = Project(
        name="TestProjekt",
        output_dir=str(tmp_path / "out"),
        settings=ProjectSettings(),
    )
    for i in range(image_count):
        fake = tmp_path / f"img_{i}.jpg"
        fake.write_bytes(b"\xff\xd8\xff" + b"\x00" * 100)
        proj.image_paths.append(str(fake))
    return proj


def _drain_queue(pipeline: Pipeline, timeout: float = 2.0) -> list:
    """Gibt alle Events aus der Queue zurück (blockiert bis DoneEvent/ErrorEvent oder Timeout)."""
    events = []
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            ev = pipeline.event_queue.get(timeout=0.05)
            events.append(ev)
            if isinstance(ev, (DoneEvent, ErrorEvent)):
                break
        except Exception:
            pass
    return events


class TestPipelineEvents:
    def test_too_few_images_raises_error_event(self, tmp_path):
        proj = _make_project(tmp_path, image_count=1)
        pipeline = Pipeline(proj)

        # Validator gibt alles als valide zurück, aber es sind < 3
        with patch("drone2map.processing.pipeline.ImageValidator") as MockVal:
            instance = MockVal.return_value
            instance.validate_batch.return_value = [
                MagicMock(valid=True, file_path=proj.image_paths[0])
            ]
            pipeline.run_async()
            events = _drain_queue(pipeline)

        assert any(isinstance(e, ErrorEvent) for e in events)
        error = next(e for e in events if isinstance(e, ErrorEvent))
        assert "valide Bilder" in error.message

    def test_stop_event_cancels_pipeline(self, tmp_path):
        proj = _make_project(tmp_path, image_count=3)
        pipeline = Pipeline(proj)

        def slow_validate(paths):
            time.sleep(0.5)
            return [MagicMock(valid=True, file_path=p) for p in paths]

        with patch("drone2map.processing.pipeline.ImageValidator") as MockVal:
            instance = MockVal.return_value
            instance.validate_batch.side_effect = slow_validate
            pipeline.run_async()
            time.sleep(0.05)
            pipeline.stop()
            events = _drain_queue(pipeline, timeout=2.0)

        # Nach stop() darf kein DoneEvent kommen
        assert not any(isinstance(e, DoneEvent) for e in events)

    def test_successful_run_emits_done_event(self, tmp_path):
        proj = _make_project(tmp_path, image_count=3)
        pipeline = Pipeline(proj)

        fake_results = {"orthophoto": "/out/orthophoto.tif"}

        with patch("drone2map.processing.pipeline.ImageValidator") as MockVal, \
             patch("drone2map.processing.pipeline.ExifParser") as MockParser, \
             patch("drone2map.processing.pipeline.OdmRunner") as MockRunner, \
             patch("drone2map.processing.pipeline.Exporter") as MockExp:

            instance_val = MockVal.return_value
            instance_val.validate_batch.return_value = [
                MagicMock(valid=True, file_path=p) for p in proj.image_paths
            ]

            instance_parser = MockParser.return_value
            mock_meta = MagicMock()
            mock_meta.latitude = 52.0
            mock_meta.longitude = 13.0
            instance_parser.parse_file.return_value = mock_meta

            instance_runner = MockRunner.return_value
            instance_runner.is_nodeodm_available.return_value = True
            instance_runner.run_via_nodeodm.return_value = fake_results

            instance_exp = MockExp.return_value
            instance_exp.export_all.return_value = fake_results
            instance_exp.create_export_report.return_value = "/out/report.txt"

            pipeline.run_async()
            events = _drain_queue(pipeline, timeout=3.0)

        assert any(isinstance(e, DoneEvent) for e in events)
        done = next(e for e in events if isinstance(e, DoneEvent))
        assert done.result_paths == fake_results

    def test_fallback_to_cli_when_nodeodm_unavailable(self, tmp_path):
        proj = _make_project(tmp_path, image_count=3)
        pipeline = Pipeline(proj)
        fake_results = {"orthophoto": "/out/orthophoto.tif"}

        with patch("drone2map.processing.pipeline.ImageValidator") as MockVal, \
             patch("drone2map.processing.pipeline.ExifParser") as MockParser, \
             patch("drone2map.processing.pipeline.OdmRunner") as MockRunner, \
             patch("drone2map.processing.pipeline.Exporter") as MockExp:

            instance_val = MockVal.return_value
            instance_val.validate_batch.return_value = [
                MagicMock(valid=True, file_path=p) for p in proj.image_paths
            ]

            instance_parser = MockParser.return_value
            mock_meta = MagicMock()
            mock_meta.latitude = 52.0
            mock_meta.longitude = 13.0
            instance_parser.parse_file.return_value = mock_meta

            instance_runner = MockRunner.return_value
            instance_runner.is_nodeodm_available.return_value = False
            instance_runner.run_via_cli.return_value = fake_results

            instance_exp = MockExp.return_value
            instance_exp.export_all.return_value = fake_results
            instance_exp.create_export_report.return_value = "/out/report.txt"

            pipeline.run_async()
            events = _drain_queue(pipeline, timeout=3.0)

        assert any(isinstance(e, DoneEvent) for e in events)
        # run_via_nodeodm darf NICHT aufgerufen worden sein
        instance_runner.run_via_nodeodm.assert_not_called()
        instance_runner.run_via_cli.assert_called_once()

    def test_odm_error_emits_error_event(self, tmp_path):
        proj = _make_project(tmp_path, image_count=3)
        pipeline = Pipeline(proj)

        with patch("drone2map.processing.pipeline.ImageValidator") as MockVal, \
             patch("drone2map.processing.pipeline.ExifParser") as MockParser, \
             patch("drone2map.processing.pipeline.OdmRunner") as MockRunner:

            instance_val = MockVal.return_value
            instance_val.validate_batch.return_value = [
                MagicMock(valid=True, file_path=p) for p in proj.image_paths
            ]
            instance_parser = MockParser.return_value
            instance_parser.parse_file.return_value = MagicMock(latitude=52.0, longitude=13.0)

            instance_runner = MockRunner.return_value
            instance_runner.is_nodeodm_available.return_value = True
            instance_runner.run_via_nodeodm.side_effect = RuntimeError("ODM timeout")

            pipeline.run_async()
            events = _drain_queue(pipeline, timeout=3.0)

        assert any(isinstance(e, ErrorEvent) for e in events)
        error = next(e for e in events if isinstance(e, ErrorEvent))
        assert "ODM timeout" in error.message
        assert proj.status == "fehler"

    def test_metadata_event_emitted(self, tmp_path):
        proj = _make_project(tmp_path, image_count=3)
        pipeline = Pipeline(proj)
        fake_results = {"orthophoto": "/out/orthophoto.tif"}

        with patch("drone2map.processing.pipeline.ImageValidator") as MockVal, \
             patch("drone2map.processing.pipeline.ExifParser") as MockParser, \
             patch("drone2map.processing.pipeline.OdmRunner") as MockRunner, \
             patch("drone2map.processing.pipeline.Exporter") as MockExp:

            instance_val = MockVal.return_value
            instance_val.validate_batch.return_value = [
                MagicMock(valid=True, file_path=p) for p in proj.image_paths
            ]
            mock_meta = MagicMock()
            mock_meta.latitude = 52.0
            mock_meta.longitude = 13.0
            instance_parser = MockParser.return_value
            instance_parser.parse_file.return_value = mock_meta

            instance_runner = MockRunner.return_value
            instance_runner.is_nodeodm_available.return_value = True
            instance_runner.run_via_nodeodm.return_value = fake_results

            instance_exp = MockExp.return_value
            instance_exp.export_all.return_value = fake_results
            instance_exp.create_export_report.return_value = "/out/report.txt"

            pipeline.run_async()
            events = _drain_queue(pipeline, timeout=3.0)

        meta_events = [e for e in events if isinstance(e, MetadataEvent)]
        assert len(meta_events) == 1
        assert len(meta_events[0].metadata) == 3

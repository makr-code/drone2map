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


class TestStageImages:
    def test_single_directory_returned_directly(self, tmp_path):
        from drone2map.processing.pipeline import Pipeline
        img1 = tmp_path / "a.jpg"
        img2 = tmp_path / "b.jpg"
        img1.write_bytes(b"")
        img2.write_bytes(b"")
        result = Pipeline._stage_images([str(img1), str(img2)], str(tmp_path))
        assert result == str(tmp_path)

    def test_multiple_directories_creates_staging(self, tmp_path):
        from drone2map.processing.pipeline import Pipeline
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        dir_a.mkdir()
        dir_b.mkdir()
        img1 = dir_a / "img.jpg"
        img2 = dir_b / "img.jpg"
        img1.write_bytes(b"aa")
        img2.write_bytes(b"bb")
        out = tmp_path / "out"
        result = Pipeline._stage_images([str(img1), str(img2)], str(out))
        staging = out / "images"
        assert result == str(staging)
        assert staging.is_dir()

    def test_staging_contains_all_images(self, tmp_path):
        from drone2map.processing.pipeline import Pipeline
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        dir_a.mkdir()
        dir_b.mkdir()
        (dir_a / "img1.jpg").write_bytes(b"1")
        (dir_b / "img2.jpg").write_bytes(b"2")
        out = tmp_path / "out"
        Pipeline._stage_images(
            [str(dir_a / "img1.jpg"), str(dir_b / "img2.jpg")], str(out))
        staged = list((out / "images").iterdir())
        assert len(staged) == 2

    def test_staging_handles_name_conflicts(self, tmp_path):
        from drone2map.processing.pipeline import Pipeline
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        dir_a.mkdir()
        dir_b.mkdir()
        (dir_a / "img.jpg").write_bytes(b"1")
        (dir_b / "img.jpg").write_bytes(b"2")
        out = tmp_path / "out"
        Pipeline._stage_images(
            [str(dir_a / "img.jpg"), str(dir_b / "img.jpg")], str(out))
        staged = list((out / "images").iterdir())
        assert len(staged) == 2

    def test_staging_idempotent_on_second_call(self, tmp_path):
        """Zweiter Aufruf mit gleichen Bildern darf keinen Fehler werfen."""
        from drone2map.processing.pipeline import Pipeline
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        dir_a.mkdir()
        dir_b.mkdir()
        (dir_a / "x.jpg").write_bytes(b"x")
        (dir_b / "y.jpg").write_bytes(b"y")
        out = tmp_path / "out"
        paths = [str(dir_a / "x.jpg"), str(dir_b / "y.jpg")]
        Pipeline._stage_images(paths, str(out))
        Pipeline._stage_images(paths, str(out))  # should not raise


class TestPipelineRetry:
    """Tests für Pipeline.retry()."""

    def test_retry_after_error_emits_done(self, tmp_path):
        """Nach einem fehlgeschlagenen Lauf soll retry() einen DoneEvent liefern."""
        proj = _make_project(tmp_path, image_count=3)
        pipeline = Pipeline(proj)
        fake_results = {"orthophoto": "/out/orthophoto.tif"}

        call_count = 0

        def validate_side_effect(paths):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Erster Versuch fehlgeschlagen")
            return [MagicMock(valid=True, file_path=p) for p in paths]

        with patch("drone2map.processing.pipeline.ImageValidator") as MockVal, \
             patch("drone2map.processing.pipeline.ExifParser") as MockParser, \
             patch("drone2map.processing.pipeline.OdmRunner") as MockRunner, \
             patch("drone2map.processing.pipeline.Exporter") as MockExp:

            MockVal.return_value.validate_batch.side_effect = validate_side_effect

            mock_meta = MagicMock(latitude=52.0, longitude=13.0)
            MockParser.return_value.parse_file.return_value = mock_meta

            MockRunner.return_value.is_nodeodm_available.return_value = True
            MockRunner.return_value.run_via_nodeodm.return_value = fake_results

            MockExp.return_value.export_all.return_value = fake_results
            MockExp.return_value.create_export_report.return_value = "/out/report.txt"

            # Erster Lauf – schlägt fehl
            pipeline.run_async()
            events_1 = _drain_queue(pipeline, timeout=2.0)
            assert any(isinstance(e, ErrorEvent) for e in events_1)

            # Retry – soll erfolgreich sein
            pipeline.retry()
            events_2 = _drain_queue(pipeline, timeout=3.0)

        assert any(isinstance(e, DoneEvent) for e in events_2)

    def test_retry_while_running_is_noop(self, tmp_path):
        """retry() darf keinen neuen Thread starten, wenn die Pipeline noch läuft."""
        proj = _make_project(tmp_path, image_count=3)
        pipeline = Pipeline(proj)

        started = threading.Event()
        blocked = threading.Event()

        def slow_validate(paths):
            started.set()
            blocked.wait(timeout=2.0)
            return [MagicMock(valid=True, file_path=p) for p in paths]

        with patch("drone2map.processing.pipeline.ImageValidator") as MockVal:
            MockVal.return_value.validate_batch.side_effect = slow_validate
            pipeline.run_async()
            started.wait(timeout=1.0)
            first_thread = pipeline._thread

            # retry() während der Thread läuft: kein neuer Thread
            pipeline.retry()
            assert pipeline._thread is first_thread

            # Aufräumen
            blocked.set()
            _drain_queue(pipeline, timeout=2.0)

    def test_retry_noop_when_no_thread(self, tmp_path):
        """retry() auf einer frischen Pipeline (kein Thread) startet run_async()."""
        proj = _make_project(tmp_path, image_count=3)
        pipeline = Pipeline(proj)

        with patch("drone2map.processing.pipeline.ImageValidator") as MockVal:
            MockVal.return_value.validate_batch.return_value = [
                MagicMock(valid=True, file_path=p) for p in proj.image_paths
            ]
            # Vor run_async() ist _thread None → retry() soll run_async() aufrufen
            pipeline.retry()
            assert pipeline._thread is not None
            _drain_queue(pipeline, timeout=2.0)

"""Tests für drone2map.processing.odm_runner."""
from __future__ import annotations
import subprocess
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from drone2map.processing.odm_runner import OdmRunner


class TestCollectResults:
    def test_empty_dir(self, tmp_path):
        results = OdmRunner._collect_results(tmp_path)
        assert results == {}

    def test_finds_orthophoto_primary(self, tmp_path):
        p = tmp_path / "odm_orthophoto"
        p.mkdir()
        (p / "odm_orthophoto.tif").write_bytes(b"")
        results = OdmRunner._collect_results(tmp_path)
        assert "orthophoto" in results
        assert results["orthophoto"].endswith("odm_orthophoto.tif")

    def test_finds_orthophoto_fallback(self, tmp_path):
        (tmp_path / "orthophoto.tif").write_bytes(b"")
        results = OdmRunner._collect_results(tmp_path)
        assert "orthophoto" in results

    def test_prefers_primary_over_fallback(self, tmp_path):
        p = tmp_path / "odm_orthophoto"
        p.mkdir()
        primary = p / "odm_orthophoto.tif"
        primary.write_bytes(b"primary")
        (tmp_path / "orthophoto.tif").write_bytes(b"fallback")
        results = OdmRunner._collect_results(tmp_path)
        assert results["orthophoto"].endswith("odm_orthophoto.tif")

    def test_finds_dsm_and_dtm(self, tmp_path):
        dem = tmp_path / "odm_dem"
        dem.mkdir()
        (dem / "dsm.tif").write_bytes(b"")
        (dem / "dtm.tif").write_bytes(b"")
        results = OdmRunner._collect_results(tmp_path)
        assert "dsm" in results
        assert "dtm" in results

    def test_finds_pointcloud(self, tmp_path):
        pc = tmp_path / "odm_pointcloud"
        pc.mkdir()
        (pc / "odm_georeferenced_model.laz").write_bytes(b"")
        results = OdmRunner._collect_results(tmp_path)
        assert "pointcloud" in results

    def test_partial_results(self, tmp_path):
        (tmp_path / "orthophoto.tif").write_bytes(b"")
        results = OdmRunner._collect_results(tmp_path)
        assert "orthophoto" in results
        assert "dsm" not in results
        assert "dtm" not in results


class TestIsNodeodmAvailable:
    def test_returns_true_when_info_succeeds(self):
        runner = OdmRunner(host="localhost", port=3000)
        with patch("drone2map.processing.odm_runner.OdmRunner.is_nodeodm_available") as mock_check:
            mock_check.return_value = True
            assert runner.is_nodeodm_available() is True

    def test_returns_false_when_pyodm_missing(self):
        runner = OdmRunner(host="localhost", port=9999)
        with patch.dict("sys.modules", {"pyodm": None}):
            result = runner.is_nodeodm_available()
        assert result is False

    def test_returns_false_on_connection_error(self):
        runner = OdmRunner(host="localhost", port=9999)
        mock_node_class = MagicMock()
        mock_node_class.return_value.info.side_effect = ConnectionError("refused")
        mock_pyodm = MagicMock()
        mock_pyodm.Node = mock_node_class
        with patch.dict("sys.modules", {"pyodm": mock_pyodm}):
            result = runner.is_nodeodm_available()
        assert result is False

    def test_returns_true_on_successful_connection(self):
        runner = OdmRunner(host="localhost", port=3000)
        mock_node_class = MagicMock()
        mock_node_class.return_value.info.return_value = MagicMock(version="1.0")
        mock_pyodm = MagicMock()
        mock_pyodm.Node = mock_node_class
        with patch.dict("sys.modules", {"pyodm": mock_pyodm}):
            result = runner.is_nodeodm_available()
        assert result is True


class TestRunViaCli:
    def test_raises_on_nonzero_exit(self, tmp_path):
        runner = OdmRunner()
        mock_proc = MagicMock()
        mock_proc.stdout = iter(["line1\n", "line2\n"])
        mock_proc.wait.return_value = 1
        mock_proc.returncode = 1
        with patch("subprocess.Popen", return_value=mock_proc):
            with pytest.raises(RuntimeError, match="exit 1"):
                runner.run_via_cli(str(tmp_path), str(tmp_path))

    def test_returns_results_on_success(self, tmp_path):
        runner = OdmRunner()
        (tmp_path / "orthophoto.tif").write_bytes(b"")
        mock_proc = MagicMock()
        mock_proc.stdout = iter([])
        mock_proc.wait.return_value = 0
        mock_proc.returncode = 0
        with patch("subprocess.Popen", return_value=mock_proc):
            results = runner.run_via_cli(str(tmp_path), str(tmp_path))
        assert "orthophoto" in results

    def test_stop_event_terminates_process(self, tmp_path):
        runner = OdmRunner()
        stop = threading.Event()

        def slow_lines():
            stop.set()
            yield "line\n"

        mock_proc = MagicMock()
        mock_proc.stdout = slow_lines()
        mock_proc.wait.return_value = 0
        mock_proc.returncode = 0
        with patch("subprocess.Popen", return_value=mock_proc):
            result = runner.run_via_cli(str(tmp_path), str(tmp_path), stop_event=stop)
        mock_proc.terminate.assert_called_once()
        assert result == {}

    def test_progress_callback_called(self, tmp_path):
        runner = OdmRunner()
        (tmp_path / "orthophoto.tif").write_bytes(b"")
        mock_proc = MagicMock()
        mock_proc.stdout = iter(["processing\n"])
        mock_proc.wait.return_value = 0
        mock_proc.returncode = 0
        calls = []
        with patch("subprocess.Popen", return_value=mock_proc):
            runner.run_via_cli(str(tmp_path), str(tmp_path),
                               progress_callback=lambda p, m: calls.append((p, m)))
        assert any(m == "processing" for _, m in calls)

    def test_default_options_used(self, tmp_path):
        runner = OdmRunner()
        mock_proc = MagicMock()
        mock_proc.stdout = iter([])
        mock_proc.wait.return_value = 0
        mock_proc.returncode = 0
        captured_cmd = []
        def fake_popen(cmd, **kwargs):
            captured_cmd.extend(cmd)
            return mock_proc
        with patch("subprocess.Popen", side_effect=fake_popen):
            runner.run_via_cli(str(tmp_path), str(tmp_path))
        assert "--dsm" in captured_cmd
        assert "--dtm" in captured_cmd


class TestRunViaNodeodmRetry:
    """Tests für die Wiederholungslogik in run_via_nodeodm."""

    def _make_mock_pyodm(self, info_side_effects, tmp_path):
        """Erstellt ein Mock-pyodm-Modul mit vordefinierten info()-Antworten."""
        mock_info_completed = MagicMock()
        mock_info_completed.progress = 100.0
        mock_info_completed.status.name = "COMPLETED"

        mock_task = MagicMock()
        mock_task.info.side_effect = info_side_effects
        mock_task.download_assets.return_value = None

        mock_node = MagicMock()
        mock_node.info.return_value = MagicMock(version="1.0")
        mock_node.create_task.return_value = mock_task

        mock_pyodm = MagicMock()
        mock_pyodm.Node.return_value = mock_node
        return mock_pyodm, mock_task

    def test_retries_transient_error_and_succeeds(self, tmp_path):
        """Nach einem transienten Fehler soll ein Retry erfolgen und danach Erfolg."""
        completed_info = MagicMock()
        completed_info.progress = 100.0
        completed_info.status.name = "COMPLETED"

        call_count = 0
        def info_side_effect():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("kurzer Ausfall")
            return completed_info

        mock_pyodm, mock_task = self._make_mock_pyodm(info_side_effect, tmp_path)
        runner = OdmRunner()
        (tmp_path / "orthophoto.tif").write_bytes(b"")
        with patch.dict("sys.modules", {"pyodm": mock_pyodm}):
            with patch("time.sleep"):
                results = runner.run_via_nodeodm(
                    [str(tmp_path / "orthophoto.tif")],
                    str(tmp_path),
                    max_retries=3,
                    retry_delay=0.0,
                )
        assert call_count == 2
        assert isinstance(results, dict)

    def test_raises_after_max_retries_exceeded(self, tmp_path):
        """Nach Überschreiten von max_retries soll RuntimeError ausgelöst werden."""
        def always_fail():
            raise ConnectionError("dauerhafter Ausfall")

        mock_pyodm, mock_task = self._make_mock_pyodm(always_fail, tmp_path)
        runner = OdmRunner()
        with patch.dict("sys.modules", {"pyodm": mock_pyodm}):
            with patch("time.sleep"):
                with pytest.raises(RuntimeError, match="Verbindung nach 2 Versuchen verloren"):
                    runner.run_via_nodeodm(
                        [str(tmp_path / "img.jpg")],
                        str(tmp_path),
                        max_retries=2,
                        retry_delay=0.0,
                    )

    def test_retry_callback_message_sent(self, tmp_path):
        """Bei einem Retry soll eine entsprechende Nachricht an den Callback gesendet werden."""
        completed_info = MagicMock()
        completed_info.progress = 100.0
        completed_info.status.name = "COMPLETED"

        call_count = 0
        def info_side_effect():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("blip")
            return completed_info

        mock_pyodm, _ = self._make_mock_pyodm(info_side_effect, tmp_path)
        runner = OdmRunner()
        (tmp_path / "orthophoto.tif").write_bytes(b"")
        messages = []
        with patch.dict("sys.modules", {"pyodm": mock_pyodm}):
            with patch("time.sleep"):
                runner.run_via_nodeodm(
                    [str(tmp_path / "orthophoto.tif")],
                    str(tmp_path),
                    max_retries=3,
                    retry_delay=0.0,
                    progress_callback=lambda _p, m: messages.append(m),
                )
        assert any("Wiederholungsversuch" in m for m in messages)

    def test_no_retry_on_completed_status(self, tmp_path):
        """COMPLETED-Status soll beim ersten info()-Aufruf sofort abschließen."""
        completed_info = MagicMock()
        completed_info.progress = 100.0
        completed_info.status.name = "COMPLETED"

        mock_pyodm, mock_task = self._make_mock_pyodm([completed_info], tmp_path)
        runner = OdmRunner()
        (tmp_path / "orthophoto.tif").write_bytes(b"")
        with patch.dict("sys.modules", {"pyodm": mock_pyodm}):
            with patch("time.sleep"):
                runner.run_via_nodeodm(
                    [str(tmp_path / "orthophoto.tif")],
                    str(tmp_path),
                )
        assert mock_task.info.call_count == 1

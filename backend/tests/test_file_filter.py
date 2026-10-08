import os
from pathlib import Path
from app.services.file_filter import file_filter_service, FileFilterService


def test_file_filter_code_vs_ignored_extensions(tmp_path):
    root = tmp_path / "test_repo"
    root.mkdir()

    # Valid source files
    py_file = root / "main.py"
    py_file.write_text("def hello():\n    return 'world'\n", encoding="utf-8")

    ts_file = root / "app.ts"
    ts_file.write_text("export const pi: number = 3.14159;\n", encoding="utf-8")

    dockerfile = root / "Dockerfile"
    dockerfile.write_text("FROM python:3.11-slim\n", encoding="utf-8")

    # Files that should be ignored
    lockfile = root / "package-lock.json"
    lockfile.write_text('{"name": "test"}', encoding="utf-8")

    minified = root / "bundle.min.js"
    minified.write_text("function a(){}", encoding="utf-8")

    # Run scan
    summary = file_filter_service.scan_repository(root)

    assert summary.eligible_count == 3
    rel_paths = [f.relative_path for f in summary.eligible_files]
    assert "main.py" in rel_paths
    assert "app.ts" in rel_paths
    assert "Dockerfile" in rel_paths
    assert "package-lock.json" not in rel_paths
    assert "bundle.min.js" not in rel_paths


def test_file_filter_skips_noisy_directories(tmp_path):
    root = tmp_path / "noisy_repo"
    root.mkdir()

    # Good source file in src/
    src_dir = root / "src"
    src_dir.mkdir()
    (src_dir / "service.py").write_text("class Service:\n    pass\n", encoding="utf-8")

    # Noise directory: node_modules
    nm_dir = root / "node_modules" / "some_pkg"
    nm_dir.mkdir(parents=True)
    (nm_dir / "index.js").write_text("module.exports = {};", encoding="utf-8")

    # Noise directory: __pycache__
    cache_dir = root / "__pycache__"
    cache_dir.mkdir()
    (cache_dir / "service.cpython-311.pyc").write_bytes(b"\x00\x00\x00\x00")

    summary = file_filter_service.scan_repository(root)

    assert summary.eligible_count == 1
    assert summary.eligible_files[0].relative_path == "src/service.py"
    assert summary.total_code_lines == 2


def test_binary_file_detection(tmp_path):
    binary_file = tmp_path / "image.bin"
    # Write null bytes to simulate binary file
    binary_file.write_bytes(b"PNG\r\n\x1a\n\x00\x00\x00\rIHDR")

    is_bin = FileFilterService.is_binary_file(binary_file)
    assert is_bin is True

    eligible, reason = FileFilterService.should_index_file(binary_file, tmp_path)
    assert eligible is False


def test_large_file_guard(tmp_path):
    large_file = tmp_path / "big_dump.sql"
    # Create file slightly exceeding 1MB
    large_file.write_bytes(b"SELECT 1;\n" * (1024 * 120))

    eligible, reason = FileFilterService.should_index_file(large_file, tmp_path)
    assert eligible is False
    assert reason == "file_too_large"

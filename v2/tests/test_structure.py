from pathlib import Path


def test_v2_root_py_files_are_only_entrypoints():
    root = Path(__file__).resolve().parents[1]
    assert sorted(p.name for p in root.glob("*.py")) == ["run.py", "serve.py"]


def test_removed_legacy_v2_paths_are_absent():
    root = Path(__file__).resolve().parents[1]
    forbidden = [
        root / "pipeline.py",
        root / "engine" / "core",
        root / "engine" / "strategies",
        root / "evaluation" / "projection",
        root / "evaluation" / "market",
        root / "assets",
    ]
    assert not any(path.exists() for path in forbidden)

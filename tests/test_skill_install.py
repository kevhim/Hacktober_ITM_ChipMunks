from pathlib import Path

import pytest

from deploy_and_benchmarks.install_skills import SKILLS, install_skills


def test_copy_installs_all_runnable_skill_folders(tmp_path):
    install_skills(tmp_path, copy=True)
    for name in SKILLS:
        assert (tmp_path / name / "SKILL.md").is_file()
        assert (tmp_path / name / "scripts" / "run_skill.py").is_file()


def test_existing_user_skill_is_preserved_before_any_changes(tmp_path):
    existing = tmp_path / "pii-leak-prober"
    existing.mkdir()
    (existing / "SKILL.md").write_text("user content", encoding="utf-8")
    with pytest.raises(FileExistsError, match="Existing skill preserved"):
        install_skills(tmp_path, copy=True)
    assert (existing / "SKILL.md").read_text() == "user content"
    assert not (tmp_path / "injection-fuzzer").exists()


def test_dry_run_does_not_create_destination(tmp_path):
    destination = tmp_path / "skills"
    assert len(install_skills(destination, dry_run=True)) == 5
    assert not destination.exists()

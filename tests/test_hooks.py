from types import SimpleNamespace

import pytest

from usr.plugins.tree_sitter import hooks


def test_expected_version_comes_from_single_exact_requirement(tmp_path, monkeypatch):
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("tree-sitter-language-pack==1.2.3\n", encoding="utf-8")
    monkeypatch.setattr(hooks, "REQUIREMENTS", requirements)

    assert hooks._expected_version() == "1.2.3"


def test_expected_version_rejects_unbounded_or_extra_dependencies(tmp_path, monkeypatch):
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("tree-sitter-language-pack>=1\nrequests==2.0\n", encoding="utf-8")
    monkeypatch.setattr(hooks, "REQUIREMENTS", requirements)

    with pytest.raises(RuntimeError, match="Unsupported"):
        hooks._expected_version()


def test_pre_update_never_installs_old_requirements(monkeypatch):
    monkeypatch.setattr(hooks, "dependency_status", lambda: {"ready": False})
    monkeypatch.setattr(
        hooks.subprocess,
        "run",
        lambda *_args, **_kwargs: pytest.fail("pre_update must not install dependencies"),
    )

    result = hooks.pre_update()

    assert result["phase"] == "pre_update"
    assert result["execution_performed"] is False


def test_install_is_idempotent_when_runtime_is_ready(monkeypatch):
    monkeypatch.setattr(hooks, "dependency_status", lambda: {"ready": True})
    monkeypatch.setattr(
        hooks,
        "_verify_parser_runtime",
        lambda: {"ok": True, "parser_count": 28},
    )
    monkeypatch.setattr(
        hooks.subprocess,
        "run",
        lambda *_args, **_kwargs: pytest.fail("ready runtime must not be reinstalled"),
    )

    result = hooks.install()

    assert result["ok"] is True
    assert result["execution_performed"] is False
    assert result["parser_matrix"]["parser_count"] == 28


def test_install_runs_pinned_command_then_rechecks_runtime(monkeypatch):
    statuses = iter(({"ready": False}, {"ready": True}))
    monkeypatch.setattr(hooks, "dependency_status", lambda: next(statuses))
    monkeypatch.setattr(hooks, "_install_command", lambda: ["uv", "pip", "install", "-r", "requirements.txt"])
    monkeypatch.setattr(
        hooks,
        "_verify_parser_runtime",
        lambda: {"ok": True, "parser_count": 28},
    )
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(hooks.subprocess, "run", fake_run)

    result = hooks.install()

    assert calls[0][0][0] == "uv"
    assert calls[0][1]["timeout"] == hooks.INSTALL_TIMEOUT_SECONDS
    assert result["execution_performed"] is True
    assert result["installer"] == "uv"
    assert result["parser_matrix"]["ok"] is True


def test_install_fails_when_native_parser_matrix_fails(monkeypatch):
    monkeypatch.setattr(hooks, "dependency_status", lambda: {"ready": True})

    def fail_matrix():
        raise RuntimeError("csharp parser failed")

    monkeypatch.setattr(hooks, "_verify_parser_runtime", fail_matrix)

    with pytest.raises(RuntimeError, match="csharp parser failed"):
        hooks.install()


def test_uninstall_does_not_remove_shared_framework_dependency():
    result = hooks.uninstall()

    assert result["shared_dependency_retained"] is True


def test_runtime_report_requires_runtime_and_exact_dependency(monkeypatch):
    monkeypatch.setattr(hooks, "dependency_status", lambda: {"ready": False})
    monkeypatch.setattr(
        "usr.plugins.tree_sitter.helpers.runtime_support.runtime_status",
        lambda: {"ready": True, "language_pack_version": "newer-but-unverified"},
    )

    result = hooks.runtime_report()

    assert result["runtime_ready"] is True
    assert result["ready"] is False

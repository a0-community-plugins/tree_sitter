from usr.plugins.tree_sitter.helpers.config import normalize_config


def test_normalize_config_applies_bounds_and_boolean_strings():
    config = normalize_config({
        "max_file_bytes": "1",
        "index_max_files": 999_999,
        "auto_refresh_index": "false",
        "auto_context_enabled": "false",
        "index_include_untracked": "yes",
    })

    assert config["max_file_bytes"] == 10_000
    assert config["index_max_files"] == 100_000
    assert config["auto_refresh_index"] is False
    assert config["auto_context_enabled"] is False
    assert config["index_include_untracked"] is True


def test_normalize_config_returns_a_complete_copy():
    first = normalize_config(None)
    second = normalize_config({})

    assert first == second
    assert first is not second

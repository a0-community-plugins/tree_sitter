"""Opt-in smoke matrix for the native parsers used by Agent Zero.

Run this test with the exact framework Python, not the agent execution runtime:

    TREE_SITTER_REAL_RUNTIME=1 python -m pytest \
        usr/plugins/tree_sitter/tests/test_real_runtime_parsers.py -q
"""

from __future__ import annotations

import os

import pytest

from usr.plugins.tree_sitter.helpers import runtime_support
from usr.plugins.tree_sitter.helpers.parser_matrix import PARSER_MATRIX, verify_parser_matrix


pytestmark = pytest.mark.skipif(
    os.environ.get("TREE_SITTER_REAL_RUNTIME") != "1",
    reason="set TREE_SITTER_REAL_RUNTIME=1 in the Agent Zero framework runtime",
)


def test_fallback_aliases_resolve_to_real_pack_languages():
    runtime = runtime_support.require_runtime()
    invalid = {
        canonical
        for canonical in runtime_support._FALLBACK_ALIASES.values()
        if not runtime.has_language(canonical)
    }

    assert invalid == set()


def test_install_time_parser_matrix():
    result = verify_parser_matrix()

    assert result["ok"] is True
    assert result["parser_count"] == len(PARSER_MATRIX)


@pytest.mark.parametrize(("language", "path", "source"), PARSER_MATRIX)
def test_real_parser_detection_and_parse(language, path, source):
    assert runtime_support.detect_language(path, source) == language
    assert runtime_support.canonicalize_language(language) == language

    tree = runtime_support.parse_source(source, language)

    assert tree.root_node.type != "ERROR"
    assert not tree.root_node.has_error

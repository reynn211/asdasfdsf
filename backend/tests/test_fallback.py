"""Unit tests for the Python fallback analyzer and post-processing helpers."""
import os
import tempfile

import main


def _write_temp_txt(content: str) -> str:
    fd, path = tempfile.mkstemp(suffix=".txt")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def test_fallback_counts_basic_tokens():
    path = _write_temp_txt("Hello world hello WORLD world")
    try:
        result = main.fallback_analyze(path, exclude_stopwords=False)
    finally:
        os.unlink(path)
    assert result["total_words"] == 5
    assert result["unique_words"] == 2
    assert result["frequencies"] == {"world": 3, "hello": 2}


def test_fallback_handles_cyrillic():
    path = _write_temp_txt("Привет мир привет МИР МИР")
    try:
        result = main.fallback_analyze(path, exclude_stopwords=False)
    finally:
        os.unlink(path)
    assert result["frequencies"] == {"мир": 3, "привет": 2}


def test_fallback_punctuation_acts_as_separator():
    path = _write_temp_txt("one,two;three. one—two!one")
    try:
        result = main.fallback_analyze(path, exclude_stopwords=False)
    finally:
        os.unlink(path)
    assert result["frequencies"] == {"one": 3, "two": 2, "three": 1}


def test_fallback_excludes_stopwords(monkeypatch):
    monkeypatch.setattr(main, "STOP_WORDS", {"the", "a"})
    path = _write_temp_txt("The cat sat on a mat. The cat.")
    try:
        result = main.fallback_analyze(path, exclude_stopwords=True)
    finally:
        os.unlink(path)
    assert "the" not in result["frequencies"]
    assert "a" not in result["frequencies"]
    assert result["frequencies"]["cat"] == 2
    # total_words counts every token, stopwords included
    assert result["total_words"] == 8


def test_post_process_min_length_filters_short_words():
    result = {
        "total_words": 10,
        "unique_words": 3,
        "frequencies": {"a": 5, "to": 3, "cat": 2},
    }
    out = main.post_process(result, min_length=3, top_n=0)
    assert out["frequencies"] == {"cat": 2}
    # original stats are untouched (frontend uses len(filtered) for "shown")
    assert out["total_words"] == 10
    assert out["unique_words"] == 3


def test_post_process_top_n_truncates_and_preserves_order():
    result = {
        "frequencies": {"a": 5, "b": 4, "c": 3, "d": 2},
    }
    out = main.post_process(result, min_length=0, top_n=2)
    assert list(out["frequencies"].keys()) == ["a", "b"]


def test_post_process_combines_min_length_and_top_n():
    result = {
        "frequencies": {"a": 5, "to": 4, "cat": 3, "dog": 2, "x": 1},
    }
    out = main.post_process(result, min_length=3, top_n=1)
    assert out["frequencies"] == {"cat": 3}


def test_post_process_no_op_when_both_zero():
    result = {"frequencies": {"a": 2, "b": 1}}
    out = main.post_process(result, min_length=0, top_n=0)
    assert out["frequencies"] == {"a": 2, "b": 1}

def test_post_process_ignore_numbers():
    result = {"frequencies": {"hello": 5, "2024": 3, "world": 2, "42": 1}}
    out = main.post_process(result, min_length=0, top_n=0, ignore_numbers=True)
    assert out["frequencies"] == {"hello": 5, "world": 2}


def test_fallback_emits_bigrams():
    path = _write_temp_txt("the quick brown the quick brown")
    try:
        result = main.fallback_analyze(path, exclude_stopwords=False, ngram=2)
    finally:
        os.unlink(path)
    assert "ngrams" in result
    bigrams = result["ngrams"]["2"]
    assert bigrams["the quick"] == 2
    assert bigrams["quick brown"] == 2
    assert bigrams["brown the"] == 1


def test_fallback_ngram_default_is_unigrams_only():
    path = _write_temp_txt("a b c d")
    try:
        result = main.fallback_analyze(path, exclude_stopwords=False)
    finally:
        os.unlink(path)
    assert "ngrams" not in result


def test_fallback_language_ru_uses_ru_stopwords():
    # "the" and "и" both appear; with language=ru only "и" should be filtered.
    path = _write_temp_txt("и и the the world")
    try:
        result = main.fallback_analyze(
            path, exclude_stopwords=True, language="ru"
        )
    finally:
        os.unlink(path)
    freqs = result["frequencies"]
    assert "и" not in freqs
    assert freqs.get("the") == 2
    assert freqs.get("world") == 1


def test_fallback_language_en_uses_en_stopwords():
    path = _write_temp_txt("и и the the world")
    try:
        result = main.fallback_analyze(
            path, exclude_stopwords=True, language="en"
        )
    finally:
        os.unlink(path)
    freqs = result["frequencies"]
    assert "the" not in freqs
    assert freqs.get("и") == 2
    assert freqs.get("world") == 1


def test_post_process_truncates_ngrams_with_top_n():
    result = {
        "frequencies": {"a": 3, "b": 2, "c": 1},
        "ngrams": {"2": {"a b": 5, "b c": 3, "c a": 1}},
    }
    out = main.post_process(result, min_length=0, top_n=2)
    assert list(out["ngrams"]["2"].keys()) == ["a b", "b c"]


def test_fallback_detects_russian_language():
    path = _write_temp_txt("Привет мир это тест русского текста")
    try:
        result = main.fallback_analyze(path, exclude_stopwords=False)
    finally:
        os.unlink(path)
    assert result["language"] == "ru"


def test_fallback_detects_english_language():
    path = _write_temp_txt("Hello world this is an english sentence")
    try:
        result = main.fallback_analyze(path, exclude_stopwords=False)
    finally:
        os.unlink(path)
    assert result["language"] == "en"


def test_fallback_language_unknown_for_numbers_only():
    path = _write_temp_txt("123 456 789 2024")
    try:
        result = main.fallback_analyze(path, exclude_stopwords=False)
    finally:
        os.unlink(path)
    assert result["language"] == "unknown"

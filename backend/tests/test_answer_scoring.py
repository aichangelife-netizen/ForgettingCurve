from app.services.answer_scoring import check_answer, normalize_answer


def test_normalize_answer_strips_outer_whitespace_and_casefolds() -> None:
    assert normalize_answer(" Memory ") == "memory"


def test_exact_answer_matches() -> None:
    assert check_answer("memory", "memory") is True


def test_leading_and_trailing_whitespace_matches() -> None:
    assert check_answer(" memory\t", "memory") is True


def test_uppercase_and_lowercase_matches() -> None:
    assert check_answer("MEMORY", "memory") is True


def test_blank_answer_is_incorrect_for_nonblank_canonical_answer() -> None:
    assert check_answer("", "memory") is False


def test_internal_space_mismatch_is_rejected() -> None:
    assert check_answer("mem ory", "memory") is False


def test_punctuation_mismatch_is_rejected() -> None:
    assert check_answer("memory.", "memory") is False


def test_synonym_is_rejected() -> None:
    assert check_answer("recollection", "memory") is False


def test_spelling_mistake_is_rejected() -> None:
    assert check_answer("memori", "memory") is False

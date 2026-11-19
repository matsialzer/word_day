import string

import pytest

from worddays.bot.texts import TEXTS


def _fields(s: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(s) if name}


@pytest.mark.parametrize("key", list(TEXTS))
def test_both_languages_with_same_placeholders(key):
    variants = TEXTS[key]
    assert set(variants) == {"ru", "uz"}, f"{key}: нужны оба языка"
    assert _fields(variants["ru"]) == _fields(variants["uz"]), f"{key}: разные плейсхолдеры"

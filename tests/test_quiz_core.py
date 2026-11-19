import random

import pytest

from worddays.core.quiz import (
    BOX_FORMATS,
    Question,
    blank_example,
    normalize,
    pick_format,
    scramble,
)
from worddays.db.models import QuizFormat

F = QuizFormat


def test_difficulty_grows_with_box():
    assert F.CHOICE_EN_RU in BOX_FORMATS[1]
    assert F.WRITE_FROM_MEMORY in BOX_FORMATS[5]
    # в первых коробках нет форматов с вводом текста, в последних - есть
    assert not {F.BUILD_WORD, F.WRITE_FROM_MEMORY} & set(BOX_FORMATS[1] + BOX_FORMATS[2])
    assert {F.BUILD_WORD, F.WRITE_FROM_MEMORY} & set(BOX_FORMATS[5])


def test_pick_format_respects_availability_and_falls_back():
    rng = random.Random(1)
    assert pick_format(1, {F.CHOICE_EN_RU}, rng) is F.CHOICE_EN_RU
    assert pick_format(1, {F.LISTENING}, rng) is F.LISTENING
    # у коробки 5 ничего не доступно -> безопасный выбор варианта
    assert pick_format(5, set(), rng) is F.CHOICE_RU_EN
    assert pick_format(1, set(), rng) is F.CHOICE_EN_RU
    for _ in range(30):  # чередование: оба формата коробки встречаются
        seen = {pick_format(1, {F.CHOICE_EN_RU, F.LISTENING}, rng) for _ in range(30)}
    assert seen == {F.CHOICE_EN_RU, F.LISTENING}


def test_blank_example():
    assert blank_example("We eat breakfast at eight.", "eat") == "We _____ breakfast at eight."
    assert blank_example("Eat well.", "eat") == "_____ well."  # регистр
    assert blank_example("She is a great cat.", "eat") is None  # внутри другого слова
    assert blank_example("He eats.", "eat") is None  # другая форма слова
    assert blank_example("Don't forget your keys.", "forget") == "Don't _____ your keys."


def test_scramble_never_equals_word():
    for seed in range(50):
        out = scramble("water", random.Random(seed))
        assert sorted(out.replace(" ", "").lower()) == sorted("water")
        assert out.replace(" ", "").lower() != "water"
    assert scramble("aaa") == "A A A"  # одинаковые буквы - нечего перемешивать


@pytest.mark.parametrize(("given", "ok"), [
    ("Water", True), ("  water ", True), ("WATER", True), ("watr", False), ("", False)])
def test_typed_answer_check(given, ok):
    q = Question(F.WRITE_FROM_MEMORY.value, 1, answer="water")
    assert q.check_text(given) is ok


def test_apostrophes_normalized():
    assert normalize("don’t") == normalize("Don't")


def test_choice_check_and_roundtrip():
    q = Question(F.CHOICE_EN_RU.value, 7, stem="cat", options=["собака", "кошка", "дом"],
                 answer="кошка")
    assert q.check_choice(1) and not q.check_choice(0)
    assert not q.check_choice(9) and not q.check_choice(-1)
    assert Question.from_dict(q.to_dict()) == q  # переживает хранение в FSM (JSON)
    assert not q.typed and Question(F.BUILD_WORD.value, 1, answer="x").typed


def test_phrase_start():
    from worddays.core.quiz import phrase_start
    assert phrase_start("I drink water every day.", "water") == "I drink …"
    assert phrase_start("Water is good.", "water") is None  # перед словом нечего заканчивать
    assert phrase_start("I like tea.", "coffee") is None

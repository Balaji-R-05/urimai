import pytest

from app.nlp.numerals import to_digits


@pytest.mark.parametrize("text,expected", [
    ("மாசம் ஐயாயிரம் ரூபாய் வரும்", "மாசம் 5000 ரூபாய் வரும்"),
    ("மாசம் பத்தாயிரம்", "மாசம் 10000"),
    ("வருஷத்துக்கு ரெண்டு லட்சம்", "வருஷத்துக்கு 200000"),
    ("2 லட்சம் வருமானம்", "200000 வருமானம்"),
    ("5 ஆயிரம்", "5000"),
    ("महीने में पाँच हज़ार", "महीने में 5000"),
    ("दो लाख सालाना", "200000 सालाना"),
    ("I earn 5000 a month", "I earn 5000 a month"),
    ("எனக்கு 42 வயசு", "எனக்கு 42 வயசு"),
])
def test_to_digits(text, expected):
    assert to_digits(text) == expected

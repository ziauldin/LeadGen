import pytest

from app.models.enums import ReplyClassification as C
from app.services.replies.classification import classify_reply


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("Yes, this sounds interesting. Can we talk next week?", C.POSITIVE),
        ("Sure, send over some times.", C.POSITIVE),
        ("We'd be keen to learn more.", C.POSITIVE),
        ("Not interested, thanks.", C.OBJECTION),
        ("Please remove me from your list.", C.UNSUBSCRIBE),
    ],
)
def test_classification_with_a_subject_line(body, expected):
    assert classify_reply(body, "Re: Quick question about Acme")[0] == expected

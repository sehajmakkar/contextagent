from brain.redact import redact


def test_redacts_known_secret_shapes():
    text = (
        "key AIza" + "A" * 35 + " and sk-" + "b" * 24 + "\n"
        "card 4242 4242 4242 4242\n"
        "Your verification code is 482913"
    )
    out, counts = redact(text)
    assert "AIza" not in out and "sk-" not in out
    assert "4242" not in out
    assert "482913" not in out and "verification code" in out  # keep the label, drop the code
    assert counts == {"api_key": 2, "card": 1, "otp": 1}


def test_leaves_normal_text_alone():
    text = "PR #482 · 4,210 users · 61.2% M1 retention · call me at 10:30 on 2026-10-21"
    assert redact(text) == (text, {})


def test_non_luhn_digit_runs_are_kept():
    assert redact("order 1234 5678 9012 3456")[0] == "order 1234 5678 9012 3456"

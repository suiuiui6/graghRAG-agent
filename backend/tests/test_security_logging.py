from security import FILE_ACCESS_TOKEN, token_log_hint


def test_token_log_hint_never_contains_secret() -> None:
    hint = token_log_hint(FILE_ACCESS_TOKEN)

    assert FILE_ACCESS_TOKEN not in hint
    assert hint == "[configured]"

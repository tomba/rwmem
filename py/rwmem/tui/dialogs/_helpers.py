"""Shared helpers for dialog modules."""


def parse_int(text: str) -> int:
    text = text.strip()
    if not text:
        raise ValueError('empty value')
    return int(text, 0)

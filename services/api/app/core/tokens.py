import re


def approx_tokens(text: str) -> int:
    return len(re.findall(r"\w+|[^\w\s]", text))

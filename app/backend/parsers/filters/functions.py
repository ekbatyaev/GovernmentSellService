import re

def normalize(text: str) -> str:
    text = str(text or "")
    text = text.replace("ё", "е").replace("Ё", "Е")
    text = re.sub(r"[\u00A0\t\r\n]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def matches(patterns, text: str):
    return [p.pattern for p in patterns if p.search(text)]
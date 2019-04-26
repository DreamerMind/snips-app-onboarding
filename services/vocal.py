
import re


def camel_case_split(identifier):
    matches = re.finditer(
        ".+?(?:(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])|$)", identifier
    )
    return [m.group(0) for m in matches]


def tts_prononcable(text):
    for _ in "_-,.:/!<>*#[]()=":
        text = text.replace(_, " ")
    text = text.replace("@", "at")
    text = text.replace("&", "and")
    text = " ".join(camel_case_split(text))
    return text.lower()

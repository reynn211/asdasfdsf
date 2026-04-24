import os

DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "stop_words.txt")


def load_stop_words(path: str = DATA_PATH) -> set[str]:
    if not os.path.isfile(path):
        return set()
    out: set[str] = set()
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            out.add(line)
    return out


STOP_WORDS = load_stop_words()

import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
DATA_PATH = os.path.join(DATA_DIR, "stop_words.txt")
DATA_PATH_RU = os.path.join(DATA_DIR, "stop_words_ru.txt")
DATA_PATH_EN = os.path.join(DATA_DIR, "stop_words_en.txt")


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


STOP_WORDS_RU = load_stop_words(DATA_PATH_RU)
STOP_WORDS_EN = load_stop_words(DATA_PATH_EN)
# Combined view — used when language is 'auto' / unknown, and kept for any
# importers that already pulled in STOP_WORDS as a single union set.
STOP_WORDS = load_stop_words(DATA_PATH) or (STOP_WORDS_RU | STOP_WORDS_EN)

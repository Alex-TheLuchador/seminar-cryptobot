import json

TRIPWIRE_KEYWORDS = frozenset({"IGNORE", "INSTRUCTIONS", "SYSTEM", "UNRESTRICTED"})
MAX_HEADLINE_LEN = 500


class TripwireError(Exception):
    def __init__(self, matched: str):
        super().__init__(matched)
        self.matched = matched


def load_headlines(path: str) -> list[str]:
    with open(path) as f:
        entries = json.load(f)
    return [entry["headline"] for entry in entries]


def sanitize(headline: str) -> str:
    """Truncate to MAX_HEADLINE_LEN, then scan for tripwire keywords. Raises TripwireError on match."""
    truncated = headline[:MAX_HEADLINE_LEN]
    upper = truncated.upper()
    for kw in TRIPWIRE_KEYWORDS:
        if kw in upper:
            raise TripwireError(kw)
    return truncated


def wrap(headline: str) -> str:
    return f"<news>{headline}</news>"


def process(path: str) -> list[str]:
    """Load, sanitize, and wrap all headlines. Raises TripwireError on the first keyword match."""
    return [wrap(sanitize(h)) for h in load_headlines(path)]

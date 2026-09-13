"""
Local, free sentiment analysis using an open-weights HuggingFace model.

Model: cardiffnlp/twitter-xlm-roberta-base-sentiment
  - Covers Arabic AND French (plus English, German, Hindi, Italian,
    Spanish, Portuguese) in a single model -- no need to juggle
    separate FR/AR models.
  - ~278M parameters, runs fine on CPU for batch/offline processing
    (a GPU would only matter if you need real-time speed on huge volumes).
  - Fully local and free after the one-time download: the first run
    downloads weights from the HuggingFace Hub (~1GB, needs internet
    once), then everything runs offline from the local cache with zero
    ongoing cost.

The pipeline is loaded lazily and cached as a module-level singleton so
you pay the model-loading cost once per process, not once per article.
"""

from dataclasses import dataclass
from typing import Optional

MODEL_NAME = "cardiffnlp/twitter-xlm-roberta-base-sentiment"

_pipeline = None  # lazy singleton


def _get_pipeline():
    global _pipeline
    if _pipeline is None:
        try:
            from transformers import pipeline
        except ImportError as e:
            raise ImportError(
                "transformers (and a backend like torch) are required for "
                "sentiment analysis. Install with:\n"
                "  pip install transformers torch --index-url https://download.pytorch.org/whl/cpu\n"
                "(CPU-only torch build keeps the install small; a GPU build works too if you have one)."
            ) from e

        print(f"Loading sentiment model '{MODEL_NAME}' (first run downloads ~1GB, "
              f"then it's cached locally and fully offline)...")
        _pipeline = pipeline("sentiment-analysis", model=MODEL_NAME, tokenizer=MODEL_NAME)
    return _pipeline


# This model's labels are "positive" / "negative" / "neutral" already,
# but we normalize just in case a future model version uses different casing.
_LABEL_MAP = {
    "positive": "positive", "pos": "positive", "label_2": "positive",
    "negative": "negative", "neg": "negative", "label_0": "negative",
    "neutral": "neutral", "label_1": "neutral",
}


@dataclass
class SentimentResult:
    sentiment: Optional[str] = None
    confidence: float = 0.0


def analyze_sentiment(text: str, max_chars: int = 512) -> SentimentResult:
    """
    Runs sentiment on `text` (title, or title+summary -- keep it short;
    the model has a token limit and news bodies can be long, so for full
    articles consider running this on the title + first paragraph
    rather than the whole body).
    """
    if not text or not text.strip():
        return SentimentResult()

    clf = _get_pipeline()
    # Truncate defensively; the tokenizer will also truncate but this
    # avoids sending huge strings through unnecessarily.
    result = clf(text[:max_chars], truncation=True)[0]
    label = _LABEL_MAP.get(result["label"].lower(), result["label"].lower())
    return SentimentResult(sentiment=label, confidence=float(result["score"]))

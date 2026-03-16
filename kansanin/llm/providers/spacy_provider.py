# llm/providers/spacy_provider.py
# version: 0.1.0
"""
spaCy провайдер для NLP-задач: токенизация, POS, NER, dependency parse.

Метод complete() предоставляет минимальную совместимость с LLMProvider.
Основной метод --- analyze().
"""
from __future__ import annotations

import logging
import time

from llm.provider import LLMResponse

log = logging.getLogger(__name__)


class SpaCyProvider:
    """Провайдер на базе spaCy для лингвистического анализа."""

    name = "spacy"

    def __init__(self, *, model_name: str = "en_core_web_sm"):
        try:
            import spacy
        except ImportError:
            raise ImportError(
                "spaCy не установлен. Установите: pip install kansanin[nlp]"
            )

        try:
            self._nlp = spacy.load(model_name)
        except OSError:
            raise OSError(
                f"Модель spaCy '{model_name}' не найдена. "
                f"Установите: python -m spacy download {model_name}"
            )
        self._model_name = model_name

    # ---- public ----

    def analyze(self, text: str) -> dict:
        """Возвращает результат NLP-анализа: токены, POS, NER, зависимости."""
        doc = self._nlp(text)
        return {
            "tokens": [
                {
                    "text": token.text,
                    "lemma": token.lemma_,
                    "pos": token.pos_,
                    "tag": token.tag_,
                    "dep": token.dep_,
                    "head": token.head.text,
                }
                for token in doc
            ],
            "entities": [
                {
                    "text": ent.text,
                    "label": ent.label_,
                    "start": ent.start_char,
                    "end": ent.end_char,
                }
                for ent in doc.ents
            ],
            "sentences": [sent.text for sent in doc.sents],
        }

    def complete(self, prompt: str, **kw) -> LLMResponse:
        """Минимальная совместимость с LLMProvider --- возвращает NLP-анализ как JSON."""
        import json

        t0 = time.monotonic()
        result = self.analyze(prompt)
        latency = (time.monotonic() - t0) * 1000

        return LLMResponse(
            text=json.dumps(result, ensure_ascii=False),
            model=self._model_name,
            usage={"prompt_tokens": 0, "completion_tokens": 0},
            provider=self.name,
            latency_ms=round(latency, 2),
        )

    def is_available(self) -> bool:
        return self._nlp is not None

    @property
    def max_context(self) -> int:
        return self._nlp.max_length

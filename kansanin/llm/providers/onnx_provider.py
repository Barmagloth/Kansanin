# llm/providers/onnx_provider.py
# version: 0.1.0
"""
ONNX Runtime провайдер для локального инференса (эмбеддинги / классификация).

Не является генеративным --- метод complete() возвращает результат
эмбеддинга или классификации в текстовом виде.
"""
from __future__ import annotations

import logging
import time

from llm.provider import LLMResponse

log = logging.getLogger(__name__)


class ONNXProvider:
    """Провайдер на базе ONNX Runtime для локальных моделей."""

    name = "onnx"

    def __init__(self, *, model_path: str | None = None):
        try:
            import onnxruntime as ort
        except ImportError:
            raise ImportError(
                "onnxruntime не установлен. Установите: pip install kansanin[llm-onnx]"
            )

        self._ort = ort
        self._model_path = model_path
        self._session = None

        if model_path is not None:
            self._session = ort.InferenceSession(model_path)

    # ---- public ----

    def complete(self, prompt: str, **kw) -> LLMResponse:
        """Возвращает результат эмбеддинга как текстовое представление вектора."""
        t0 = time.monotonic()
        vectors = self.embed([prompt])
        latency = (time.monotonic() - t0) * 1000

        text = str(vectors[0]) if vectors else "[]"
        return LLMResponse(
            text=text,
            model=self._model_path or "onnx-unknown",
            usage={"prompt_tokens": 0, "completion_tokens": 0},
            provider=self.name,
            latency_ms=round(latency, 2),
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Вычисляет эмбеддинги для списка текстов."""
        if self._session is None:
            raise RuntimeError(
                "ONNX-сессия не инициализирована --- укажите model_path"
            )
        import numpy as np

        input_name = self._session.get_inputs()[0].name
        results: list[list[float]] = []
        for text in texts:
            # Минимальная токенизация: передаём текст как массив байт/ID
            # Реальная токенизация зависит от конкретной модели
            input_data = np.array([[ord(c) for c in text[:512]]], dtype=np.int64)
            outputs = self._session.run(None, {input_name: input_data})
            embedding = outputs[0].flatten().tolist()
            results.append(embedding)
        return results

    def is_available(self) -> bool:
        return self._session is not None

    @property
    def max_context(self) -> int:
        return 512

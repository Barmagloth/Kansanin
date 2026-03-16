# llm/config.py
# version: 0.1.0
"""
Загрузка конфигурации Kansanin LLM/NLP.

Приоритет (от низкого к высокому):
  1. Значения по умолчанию (dataclass defaults)
  2. Файл .kansanin.yaml (текущая директория -> родительские -> ~/.config/kansanin/)
  3. Переменные окружения KANSANIN_*
  4. CLI-переопределения (dict)
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

_TRUTHY = frozenset({"1", "true", "yes"})


# ---- dataclasses ----

@dataclass
class LLMConfig:
    enabled: bool = False
    provider: str = "openai"
    model: str = "gpt-4o"
    temperature: float = 0.0
    max_tokens: int = 2048
    timeout_seconds: int = 30
    detectors: dict[str, dict] = field(default_factory=dict)


@dataclass
class NLPConfig:
    enabled: bool = False
    spacy_model: str = "en_core_web_sm"
    detectors: dict[str, dict] = field(default_factory=dict)


@dataclass
class KansaninConfig:
    llm: LLMConfig = field(default_factory=LLMConfig)
    nlp: NLPConfig = field(default_factory=NLPConfig)


# ---- поиск конфиг-файла ----

_CONFIG_NAMES = (".kansanin.yaml", ".kansanin.yml")


def _find_config_file() -> Path | None:
    """Ищет .kansanin.yaml от cwd вверх до корня, затем ~/.config/kansanin/."""
    cwd = Path.cwd().resolve()
    for directory in (cwd, *cwd.parents):
        for name in _CONFIG_NAMES:
            candidate = directory / name
            if candidate.is_file():
                return candidate
    # fallback: ~/.config/kansanin/config.yaml
    home_cfg = Path.home() / ".config" / "kansanin" / "config.yaml"
    if home_cfg.is_file():
        return home_cfg
    return None


def _load_yaml_file(path: Path) -> dict:
    """Загружает YAML-файл. Возвращает пустой dict при ошибке."""
    try:
        import yaml
    except ImportError:
        log.warning("PyYAML не установлен --- конфиг-файл %s пропущен", path)
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        log.warning("Ошибка чтения конфиг-файла %s: %s", path, exc)
        return {}


# ---- слияние слоёв ----

def _apply_file(cfg: KansaninConfig, data: dict) -> None:
    """Применяет данные из YAML-файла к конфигу."""
    llm_data = data.get("llm", {})
    if isinstance(llm_data, dict):
        for key in ("enabled", "provider", "model", "temperature",
                     "max_tokens", "timeout_seconds"):
            if key in llm_data:
                setattr(cfg.llm, key, llm_data[key])
        if "detectors" in llm_data and isinstance(llm_data["detectors"], dict):
            cfg.llm.detectors.update(llm_data["detectors"])

    nlp_data = data.get("nlp", {})
    if isinstance(nlp_data, dict):
        for key in ("enabled", "spacy_model"):
            if key in nlp_data:
                setattr(cfg.nlp, key, nlp_data[key])
        if "detectors" in nlp_data and isinstance(nlp_data["detectors"], dict):
            cfg.nlp.detectors.update(nlp_data["detectors"])


def _apply_env(cfg: KansaninConfig) -> None:
    """Применяет переменные окружения KANSANIN_*."""
    val = os.environ.get("KANSANIN_LLM_ENABLED")
    if val is not None:
        cfg.llm.enabled = val.lower() in _TRUTHY

    val = os.environ.get("KANSANIN_LLM_PROVIDER")
    if val:
        cfg.llm.provider = val

    val = os.environ.get("KANSANIN_LLM_MODEL")
    if val:
        cfg.llm.model = val

    val = os.environ.get("KANSANIN_NLP_ENABLED")
    if val is not None:
        cfg.nlp.enabled = val.lower() in _TRUTHY


def _apply_cli(cfg: KansaninConfig, overrides: dict) -> None:
    """Применяет CLI-переопределения (плоский dict)."""
    mapping = {
        "llm_enabled":        lambda v: setattr(cfg.llm, "enabled", bool(v)),
        "llm_provider":       lambda v: setattr(cfg.llm, "provider", str(v)),
        "llm_model":          lambda v: setattr(cfg.llm, "model", str(v)),
        "llm_temperature":    lambda v: setattr(cfg.llm, "temperature", float(v)),
        "llm_max_tokens":     lambda v: setattr(cfg.llm, "max_tokens", int(v)),
        "llm_timeout":        lambda v: setattr(cfg.llm, "timeout_seconds", int(v)),
        "nlp_enabled":        lambda v: setattr(cfg.nlp, "enabled", bool(v)),
        "nlp_spacy_model":    lambda v: setattr(cfg.nlp, "spacy_model", str(v)),
    }
    for key, value in overrides.items():
        setter = mapping.get(key)
        if setter is not None:
            setter(value)


# ---- публичный интерфейс ----

def load_config(cli_overrides: dict | None = None) -> KansaninConfig:
    """Собирает конфигурацию из всех источников (4 уровня приоритета)."""
    cfg = KansaninConfig()

    # слой 2: файл
    config_path = _find_config_file()
    if config_path is not None:
        log.debug("Загружается конфиг из %s", config_path)
        _apply_file(cfg, _load_yaml_file(config_path))

    # слой 3: env
    _apply_env(cfg)

    # слой 4: CLI
    if cli_overrides:
        _apply_cli(cfg, cli_overrides)

    return cfg

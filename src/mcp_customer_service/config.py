"""Gestion de la configuration pour le serveur MCP."""
from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Optional

from pydantic import BaseSettings, Field, validator


class Settings(BaseSettings):
    """Paramètres du serveur MCP."""

    openai_api_key: str = Field(
        default="",
        description="Clé API OpenAI utilisée pour appeler ChatGPT.",
        env="OPENAI_API_KEY",
    )
    composio_api_key: str = Field(
        default="",
        description="Clé API Composio pour orchestrer les intégrations.",
        env="COMPOSIO_API_KEY",
    )
    default_model: str = Field(
        default="gpt-4o-mini",
        env="DEFAULT_MODEL",
        description="Modèle OpenAI utilisé par défaut pour générer les réponses.",
    )
    max_history_messages: int = Field(
        default=6,
        ge=1,
        description="Nombre de messages précédents envoyés au modèle pour le contexte.",
    )
    enable_debug_traces: bool = Field(
        default=False,
        env="ENABLE_DEBUG_TRACES",
        description="Active les traces détaillées dans les réponses MCP.",
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    @validator("openai_api_key", "composio_api_key", pre=True)
    def _clean_api_keys(cls, value: Optional[str]) -> str:
        if value is None:
            return ""
        return value.strip()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Retourne les paramètres mis en cache."""

    settings = Settings()
    logging.getLogger(__name__).debug("Configuration chargée: %s", settings.dict())
    return settings


__all__ = ["Settings", "get_settings"]

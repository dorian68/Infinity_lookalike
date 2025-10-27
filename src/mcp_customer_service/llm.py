"""Client LLM basé sur l'API OpenAI."""
from __future__ import annotations

import logging
from typing import Iterable, List

from openai import OpenAI

from .config import Settings, get_settings

logger = logging.getLogger(__name__)


class ChatGPTClient:
    """Encapsulation des appels au modèle OpenAI ChatGPT."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        if not self.settings.openai_api_key:
            logger.warning(
                "Aucune clé API OpenAI détectée. Le serveur fonctionnera en mode simulation."
            )
            self._client: OpenAI | None = None
        else:
            self._client = OpenAI(api_key=self.settings.openai_api_key)

    def generate_reply(self, messages: Iterable[dict]) -> str:
        """Génère une réponse en utilisant le modèle spécifié."""

        message_list: List[dict] = list(messages)
        if not self._client:
            logger.debug("Génération simulée pour %d messages", len(message_list))
            return (
                "[SIMULATION] Merci pour votre message. Un conseiller vous répondra "
                "rapidement."
            )

        logger.debug(
            "Envoi de %d messages au modèle %s",
            len(message_list),
            self.settings.default_model,
        )
        response = self._client.chat.completions.create(
            model=self.settings.default_model,
            messages=message_list,
            temperature=0.2,
        )
        choice = response.choices[0]
        reply = choice.message.content or ""
        logger.info("Réponse générée (fin=%s) : %s", choice.finish_reason, reply)
        return reply


__all__ = ["ChatGPTClient"]

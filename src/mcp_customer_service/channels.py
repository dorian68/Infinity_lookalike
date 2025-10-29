"""Gestion des messages multi-canaux pour l'agent."""
from __future__ import annotations

import datetime as dt
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional

from pydantic import BaseModel, Field


class SupportChannel(str, Enum):
    """Enumération des canaux supportés via Composio."""

    whatsapp = "whatsapp"
    linkedin = "linkedin"
    gmail = "gmail"
    outlook = "outlook"
    instagram = "instagram"


class ConversationMessage(BaseModel):
    """Représente un message dans l'historique de la conversation."""

    role: str
    content: str
    timestamp: dt.datetime = Field(
        default_factory=lambda: dt.datetime.now(dt.timezone.utc)
    )


class CustomerPayload(BaseModel):
    """Requête provenant d'un canal client."""

    channel: SupportChannel
    customer_id: str
    thread_id: Optional[str] = None
    message: str
    history: List[ConversationMessage] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentReply(BaseModel):
    """Réponse formatée par l'agent."""

    channel: SupportChannel
    reply: str
    actions: List[str] = Field(default_factory=list)
    context: Dict[str, Any] = Field(default_factory=dict)


def build_llm_messages(payload: CustomerPayload, insights: Iterable[str]) -> List[dict]:
    """Transforme la requête en format compatible avec OpenAI."""

    messages: List[dict] = [
        {
            "role": "system",
            "content": (
                "Tu es Infinity, un agent IA de relation client multicanal "
                "capable de répondre sur WhatsApp, LinkedIn, Gmail, Outlook et "
                "Instagram. Sois empathique, concis et propose des actions "
                "concrètes adaptées au canal. Utilise les informations "
                "contextuelles pour personnaliser la réponse."
            ),
        }
    ]

    for hist in payload.history[-5:]:
        messages.append({"role": hist.role, "content": hist.content})

    if insights:
        messages.append(
            {
                "role": "system",
                "content": "Informations contextuelles: " + " | ".join(insights),
            }
        )

    messages.append({"role": "user", "content": payload.message})
    return messages


__all__ = [
    "SupportChannel",
    "ConversationMessage",
    "CustomerPayload",
    "AgentReply",
    "build_llm_messages",
]

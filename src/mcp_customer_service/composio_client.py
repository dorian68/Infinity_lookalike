"""Intégration avec Composio pour enrichir le contexte client et distribuer les réponses."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .config import Settings, get_settings
from .channels import SupportChannel

logger = logging.getLogger(__name__)

try:  # pragma: no cover - dépendance optionnelle
    from composio import Composio
except Exception:  # pragma: no cover - gestion douce des imports
    Composio = None  # type: ignore[assignment]


class ComposioClient:
    """Client léger autour du SDK Composio."""

    CHANNEL_CONNECTORS: Dict[SupportChannel, Dict[str, str]] = {
        SupportChannel.whatsapp: {
            "connector": "whatsapp",
            "action": "send_message",
            "handle_param": "phone_number",
        },
        SupportChannel.linkedin: {
            "connector": "linkedin",
            "action": "send_message",
            "handle_param": "profile_url",
        },
        SupportChannel.gmail: {
            "connector": "gmail",
            "action": "send_email",
            "handle_param": "to",
        },
        SupportChannel.outlook: {
            "connector": "outlook",
            "action": "send_email",
            "handle_param": "to",
        },
        SupportChannel.instagram: {
            "connector": "instagram",
            "action": "send_dm",
            "handle_param": "username",
        },
    }

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = None
        if not self.settings.composio_api_key or Composio is None:
            if Composio is None:
                logger.warning(
                    "Le package composio n'est pas installé. Retour en mode simulation."
                )
            else:
                logger.warning(
                    "Aucune clé API Composio détectée. Utilisation d'un mode simulé."
                )
        else:
            try:
                self._client = Composio(api_key=self.settings.composio_api_key)
            except Exception as exc:  # pragma: no cover
                logger.error("Impossible d'initialiser Composio: %s", exc)
                self._client = None

    # ---------------------------------------------------------------------
    # Découverte de contexte
    def enrich_context(self, channel: str, customer_id: str, message: str) -> Dict[str, Any]:
        """Retourne des informations supplémentaires liées au client."""

        if not self._client:
            logger.debug(
                "Enrichissement simulé pour customer_id=%s channel=%s", customer_id, channel
            )
            return {
                "customer_id": customer_id,
                "channel": channel,
                "insights": [
                    "Client premium avec historique d'achats récurrents",
                    "Dernière interaction il y a 5 jours",
                ],
                "knowledge_base_matches": [],
            }

        logger.debug(
            "Interrogation de Composio pour customer_id=%s channel=%s", customer_id, channel
        )
        knowledge_hits: List[Dict[str, Any]] = []
        try:
            knowledge_hits = self._client.knowledge.search(
                query=message,
                metadata={"channel": channel, "customer_id": customer_id},
            )
        except Exception as exc:  # pragma: no cover
            logger.error("Erreur Composio lors de la recherche de connaissances: %s", exc)

        return {
            "customer_id": customer_id,
            "channel": channel,
            "insights": self._build_insights(knowledge_hits),
            "knowledge_base_matches": knowledge_hits,
        }

    @staticmethod
    def _build_insights(knowledge_hits: List[Dict[str, Any]]) -> List[str]:
        """Synthétise les informations renvoyées par Composio."""

        insights: List[str] = []
        for hit in knowledge_hits:
            title = hit.get("title")
            summary = hit.get("summary") or hit.get("content")
            if title and summary:
                insights.append(f"{title}: {summary}")
            elif title:
                insights.append(title)
            elif summary:
                insights.append(summary)
        return insights

    # ------------------------------------------------------------------
    # Découverte des connecteurs et actions disponibles
    def list_available_tools(self) -> Dict[str, Any]:
        """Inspecte Composio pour vérifier l'accès aux connecteurs configurés."""

        mode = "live" if self._client else "simulated"
        status: List[Dict[str, Any]] = []
        for channel, spec in self.CHANNEL_CONNECTORS.items():
            channel_status: Dict[str, Any] = {
                "channel": channel.value,
                "connector": spec["connector"],
                "action": spec["action"],
            }
            if not self._client:
                channel_status.update(
                    {
                        "available": False,
                        "reason": "Mode simulation: clé API ou SDK Composio manquant.",
                    }
                )
            else:
                available, reason = self._inspect_connector(spec["connector"], spec["action"])
                channel_status["available"] = available
                if reason:
                    channel_status["reason"] = reason
            status.append(channel_status)

        return {"mode": mode, "connectors": status}

    def _inspect_connector(self, connector_slug: str, action_name: str) -> tuple[bool, Optional[str]]:
        """Valide que le connecteur et l'action sont exposés par Composio."""

        issues: List[str] = []
        connector_found = False
        action_found = False

        if not self._client:
            return False, "Client Composio inactif"

        # Vérifie la présence du connecteur
        connectors_client = getattr(self._client, "connectors", None)
        if connectors_client and hasattr(connectors_client, "list"):
            try:
                connectors = connectors_client.list()
                connector_found = self._entry_in_collection(
                    connector_slug, connectors, keys=("slug", "name", "connector", "id")
                )
                if not connector_found:
                    issues.append("Connecteur introuvable dans l'espace Composio")
            except Exception as exc:  # pragma: no cover - dépend des implémentations SDK
                issues.append(f"Impossible d'interroger les connecteurs: {exc}")
        else:
            issues.append("La méthode connectors.list() n'est pas disponible")

        # Vérifie la présence de l'action
        actions_client = getattr(self._client, "actions", None)
        if actions_client and hasattr(actions_client, "list"):
            try:
                try:
                    actions = actions_client.list(connector=connector_slug)
                except TypeError:
                    actions = actions_client.list()
                action_found = self._entry_in_collection(
                    action_name, actions, keys=("name", "action", "slug", "id")
                )
                if not action_found:
                    issues.append("Action introuvable pour ce connecteur")
            except Exception as exc:  # pragma: no cover
                issues.append(f"Impossible d'interroger les actions: {exc}")
        else:
            issues.append("La méthode actions.list() n'est pas disponible")

        available = connector_found and action_found
        reason = "; ".join(dict.fromkeys(issues)) if issues else None
        return available, reason

    @staticmethod
    def _entry_in_collection(expected: str, collection: Any, keys: tuple[str, ...]) -> bool:
        """Détermine si une valeur correspondante est présente dans une collection."""

        if not collection:
            return False

        expected_lower = expected.lower()
        for item in ComposioClient._normalize_collection(collection):
            for value in ComposioClient._extract_values(item, keys):
                value_lower = value.lower()
                if (
                    value_lower == expected_lower
                    or value_lower.endswith(expected_lower)
                    or expected_lower in value_lower
                ):
                    return True
        return False

    @staticmethod
    def _normalize_collection(collection: Any) -> List[Any]:
        """Aplati différentes structures renvoyées par le SDK Composio."""

        if isinstance(collection, dict):
            if "items" in collection and isinstance(collection["items"], list):
                return list(collection["items"])
            return [collection]
        if isinstance(collection, (list, tuple, set)):
            return list(collection)
        return [collection]

    @staticmethod
    def _extract_values(item: Any, keys: tuple[str, ...]) -> List[str]:
        """Récupère les valeurs texte pertinentes d'un élément de collection."""

        values: List[str] = []
        if isinstance(item, str):
            values.append(item)
            return values

        if isinstance(item, dict):
            for key in keys:
                value = item.get(key)
                if isinstance(value, str):
                    values.append(value)
            return values

        for key in keys:
            value = getattr(item, key, None)
            if isinstance(value, str):
                values.append(value)
        return values

    def dispatch_reply(
        self,
        channel: SupportChannel,
        message: str,
        customer_handle: Optional[str],
        thread_id: Optional[str] = None,
        subject: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Envoie la réponse générée sur le canal approprié."""

        connector_spec = self.CHANNEL_CONNECTORS.get(channel)
        if connector_spec is None:
            return {
                "status": "unsupported",
                "reason": f"Canal {channel.value} non configuré pour la diffusion",
            }

        if not customer_handle:
            return {
                "status": "missing-handle",
                "reason": "Aucun identifiant client fourni pour l'envoi",
                "connector": connector_spec["connector"],
            }

        payload: Dict[str, Any] = {
            connector_spec["handle_param"]: customer_handle,
            "message": message,
        }
        if thread_id:
            payload["thread_id"] = thread_id
        if subject and channel in {SupportChannel.gmail, SupportChannel.outlook}:
            payload.setdefault("subject", subject)

        if not self._client:
            logger.debug(
                "Diffusion simulée sur %s pour %s", connector_spec["connector"], customer_handle
            )
            return {
                "status": "simulated",
                "connector": connector_spec["connector"],
                "payload": payload,
            }

        try:
            logger.info(
                "Envoi via Composio connector=%s action=%s",
                connector_spec["connector"],
                connector_spec["action"],
            )
            result = self._client.actions.execute(  # type: ignore[union-attr]
                connector=connector_spec["connector"],
                action=connector_spec["action"],
                params=payload,
            )
            return {
                "status": "sent",
                "connector": connector_spec["connector"],
                "result": result,
            }
        except Exception as exc:  # pragma: no cover
            logger.error("Erreur lors de l'envoi via Composio: %s", exc)
            return {
                "status": "error",
                "connector": connector_spec["connector"],
                "error": str(exc),
            }


__all__ = ["ComposioClient"]

"""Serveur MCP représentant un agent IA de relation client multicanal."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .channels import AgentReply, CustomerPayload, SupportChannel, build_llm_messages
from .composio_client import ComposioClient
from .config import Settings, get_settings
from .llm import ChatGPTClient

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class MCPCommand(BaseModel):
    """Commande conforme au protocole MCP."""

    command: str = Field(..., description="Nom de la commande MCP demandée")
    payload: CustomerPayload


class MCPEnvelope(BaseModel):
    """Enveloppe standardisée pour les réponses."""

    status: Literal["ok", "error"]
    data: Dict[str, Any] | None = None
    diagnostics: List[str] = Field(default_factory=list)


class MultiChannelCustomerAgent:
    """Agent orchestrant l'accès au LLM et à Composio."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.llm = ChatGPTClient(self.settings)
        self.composio = ComposioClient(self.settings)

    def handle_reply(self, payload: CustomerPayload) -> AgentReply:
        context = self.composio.enrich_context(
            channel=payload.channel.value,
            customer_id=payload.customer_id,
            message=payload.message,
        )
        messages = build_llm_messages(payload, context.get("insights", []))
        reply = self.llm.generate_reply(messages)
        actions = self._suggest_actions(payload, context)
        delivery = self._dispatch_reply(payload, reply)
        if delivery:
            context.setdefault("delivery", delivery)
        return AgentReply(channel=payload.channel, reply=reply, actions=actions, context=context)

    @staticmethod
    def _suggest_actions(payload: CustomerPayload, context: Dict[str, Any]) -> List[str]:
        """Propose quelques actions suivant le contexte."""

        actions: List[str] = []
        sentiment = payload.metadata.get("sentiment")
        urgency = payload.metadata.get("urgency")
        if urgency == "high":
            actions.append("Escalader vers un superviseur humain")
        if payload.channel in {SupportChannel.gmail, SupportChannel.outlook}:
            actions.append("Joindre un suivi par email avec le récapitulatif")
        if payload.channel == SupportChannel.whatsapp:
            actions.append("Proposer une confirmation instantanée sur WhatsApp")
        if payload.channel == SupportChannel.linkedin:
            actions.append("Partager des ressources professionnelles adaptées sur LinkedIn")
        if payload.channel == SupportChannel.instagram:
            actions.append("Inclure un visuel ou une story pour renforcer le message")
        if sentiment == "negative":
            actions.append("Offrir un geste commercial")
        if not actions:
            actions.append("Consigner la conversation dans le CRM")
        return actions

    def _dispatch_reply(self, payload: CustomerPayload, reply: str) -> Dict[str, Any] | None:
        """Envoie la réponse sur le canal demandé via Composio."""

        customer_handle = self._resolve_destination(payload)
        subject = payload.metadata.get("subject")
        delivery = self.composio.dispatch_reply(
            channel=payload.channel,
            message=reply,
            customer_handle=customer_handle,
            thread_id=payload.thread_id,
            subject=subject,
        )
        return delivery

    @staticmethod
    def _resolve_destination(payload: CustomerPayload) -> str | None:
        """Détermine l'identifiant du client en fonction du canal."""

        metadata = payload.metadata
        if payload.channel == SupportChannel.whatsapp:
            return metadata.get("whatsapp_number") or metadata.get("phone_number")
        if payload.channel == SupportChannel.linkedin:
            return metadata.get("linkedin_profile") or metadata.get("profile_url")
        if payload.channel == SupportChannel.gmail:
            return metadata.get("gmail_address") or metadata.get("email")
        if payload.channel == SupportChannel.outlook:
            return metadata.get("outlook_address") or metadata.get("email")
        if payload.channel == SupportChannel.instagram:
            return metadata.get("instagram_handle") or metadata.get("username")
        return None


def build_app(settings: Settings | None = None) -> FastAPI:
    """Construit une application FastAPI exposant l'agent MCP."""

    settings = settings or get_settings()
    agent = MultiChannelCustomerAgent(settings)
    app = FastAPI(
        title="Infinity MCP Customer Service Agent",
        version="0.1.0",
        description="Agent multicanal basé sur ChatGPT et Composio.",
    )

    @app.get("/health", tags=["health"])
    async def health_check() -> Dict[str, str]:
        return {"status": "ok"}

    @app.get("/mcp/v1/metadata", tags=["mcp"])
    async def metadata() -> Dict[str, Any]:
        return {
            "name": "infinity-customer-agent",
            "version": "0.1.0",
            "capabilities": ["customer-support", "multichannel", "knowledge-integration"],
            "llm_model": settings.default_model,
            "connectors": agent.composio.list_available_tools(),
        }

    @app.get("/mcp/v1/connectors", tags=["mcp"])
    async def connectors() -> Dict[str, Any]:
        """Expose l'état des connecteurs Composio configurés."""

        return agent.composio.list_available_tools()

    @app.post("/mcp/v1/execute", response_model=MCPEnvelope, tags=["mcp"])
    async def execute(command: MCPCommand) -> MCPEnvelope:
        logger.info("Commande MCP reçue: %s", command.command)
        if command.command != "customer-agent.reply":
            raise HTTPException(status_code=400, detail="Commande MCP inconnue")

        reply = agent.handle_reply(command.payload)
        envelope = MCPEnvelope(
            status="ok",
            data={"reply": reply.dict()},
        )
        if settings.enable_debug_traces:
            envelope.diagnostics.append("Messages envoyés au LLM: %d" % len(command.payload.history))
        return envelope

    @app.exception_handler(Exception)
    async def handle_exception(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Erreur serveur", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content=MCPEnvelope(status="error", diagnostics=[str(exc)]).dict(),
        )

    return app


def main() -> None:  # pragma: no cover - point d'entrée
    import uvicorn

    uvicorn.run("mcp_customer_service.server:build_app", factory=True, host="0.0.0.0", port=8000)


if __name__ == "__main__":  # pragma: no cover
    main()

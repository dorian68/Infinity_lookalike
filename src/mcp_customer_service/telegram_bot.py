"""Bot Telegram permettant de piloter l'agent MCP en conditions réelles."""
from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional

from .channels import ConversationMessage, CustomerPayload, SupportChannel
from .config import Settings, get_settings
from .server import MultiChannelCustomerAgent

try:  # pragma: no cover - dépendance optionnelle
    from telegram import Update
    from telegram.constants import ParseMode
    from telegram.ext import (
        Application,
        CommandHandler,
        ContextTypes,
        MessageHandler,
        filters,
    )
except Exception as exc:  # pragma: no cover - gestion douce des imports
    Update = None  # type: ignore[assignment]
    ParseMode = None  # type: ignore[assignment]
    Application = None  # type: ignore[assignment]
    CommandHandler = None  # type: ignore[assignment]
    ContextTypes = None  # type: ignore[assignment]
    MessageHandler = None  # type: ignore[assignment]
    filters = None  # type: ignore[assignment]
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


logger = logging.getLogger(__name__)


@dataclass
class SessionState:
    """Historique et configuration spécifique à un utilisateur Telegram."""

    channel: SupportChannel = SupportChannel.gmail
    history: Deque[ConversationMessage] = field(
        default_factory=lambda: deque(maxlen=10)
    )
    metadata: Dict[str, str] = field(default_factory=dict)

    def to_history(self) -> List[ConversationMessage]:
        return list(self.history)


class TelegramCustomerAgentBot:
    """Wrappe python-telegram-bot pour interroger l'agent MCP."""

    def __init__(self, token: str, settings: Optional[Settings] = None) -> None:
        if Application is None:  # pragma: no cover - dépend de l'installation locale
            raise RuntimeError(
                "python-telegram-bot n'est pas installé: %s" % (_IMPORT_ERROR,)
            )

        self.settings = settings or get_settings()
        self.agent = MultiChannelCustomerAgent(self.settings)
        self.token = token
        self.sessions: Dict[int, SessionState] = {}
        self.application = Application.builder().token(token).build()

        self.application.add_handler(CommandHandler("start", self.cmd_start))
        self.application.add_handler(CommandHandler("help", self.cmd_help))
        self.application.add_handler(CommandHandler("channel", self.cmd_channel))
        self.application.add_handler(CommandHandler("connect", self.cmd_connect))
        self.application.add_handler(CommandHandler("installations", self.cmd_installations))
        self.application.add_handler(CommandHandler("status", self.cmd_status))
        self.application.add_handler(CommandHandler("setmeta", self.cmd_setmeta))
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )

    # ------------------------------------------------------------------
    # Gestion des commandes
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(
            (
                "Bonjour! Je suis l'agent client Infinity. "
                "Utilisez /channel <canal> pour choisir le canal cible (whatsapp, "
                "linkedin, gmail, outlook, instagram).\n"
                "Partagez ensuite un message et je vous répondrai comme si la "
                "conversation se déroulait sur ce canal.\n"
                "Commandes utiles :\n"
                "• /connect <canal> : obtenir un lien Composio pour connecter votre compte\n"
                "• /installations : voir les connexions existantes\n"
                "• /status : vérifier l'état des connecteurs\n"
                "• /setmeta <clé> <valeur> : fournir un identifiant client (ex: gmail_address)"
            )
        )

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self.cmd_start(update, context)

    async def cmd_channel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not context.args:
            await update.message.reply_text(
                "Veuillez préciser un canal: whatsapp, linkedin, gmail, outlook ou instagram."
            )
            return

        channel_name = context.args[0].lower()
        try:
            channel = SupportChannel(channel_name)
        except ValueError:
            await update.message.reply_text(
                f"Canal inconnu '{channel_name}'. Choisissez parmi: "
                f"{', '.join(c.value for c in SupportChannel)}"
            )
            return

        state = self._get_state(update.effective_chat.id)
        state.channel = channel
        await update.message.reply_text(
            f"Canal par défaut défini sur {channel.value}."
        )

    async def cmd_connect(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not context.args:
            await update.message.reply_text(
                "Usage : /connect <canal>."
            )
            return

        channel_name = context.args[0].lower()
        try:
            channel = SupportChannel(channel_name)
        except ValueError:
            await update.message.reply_text(
                f"Canal inconnu '{channel_name}'."
            )
            return

        user_id = str(update.effective_user.id)
        link_info = self.agent.composio.generate_installation_link(
            channel=channel, external_user_id=user_id
        )

        if link_info.get("status") == "error":
            await update.message.reply_text(
                f"Impossible de générer le lien: {link_info.get('reason', 'erreur inconnue')}"
            )
            return

        url = link_info.get("url") or link_info.get("authorization_url")
        if not url:
            await update.message.reply_text(
                "Lien reçu mais aucune URL n'est disponible. Vérifiez votre configuration Composio."
            )
            return

        await update.message.reply_text(
            (
                f"Connectez votre compte {channel.value} via Composio :\n{url}\n"
                "Une fois l'installation terminée, utilisez /installations pour vérifier."
            ),
            disable_web_page_preview=False,
        )

    async def cmd_installations(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = str(update.effective_user.id)
        info = self.agent.composio.list_user_installations(user_id)

        if info.get("status") == "error":
            await update.message.reply_text(
                f"Erreur lors de la récupération des installations: {info.get('reason', 'inconnue')}"
            )
            return

        installations = info.get("installations", [])
        if not installations:
            await update.message.reply_text("Aucune installation Composio détectée pour le moment.")
            return

        lines = ["Installations Composio associées à votre compte:"]
        for idx, item in enumerate(installations, start=1):
            connector = item.get("connector") or item.get("integration") or item.get("name")
            status = item.get("status") or item.get("state")
            lines.append(f"{idx}. {connector or 'inconnu'} — {status or 'actif'}")
        await update.message.reply_text("\n".join(lines))

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        info = self.agent.composio.list_available_tools()
        lines = [f"Mode Composio: {info.get('mode')}" , "Connecteurs:" ]
        for entry in info.get("connectors", []):
            status = "✅" if entry.get("available") else "❌"
            reason = entry.get("reason")
            line = f"{status} {entry['channel']} → {entry['connector']}/{entry['action']}"
            if reason:
                line += f" ({reason})"
            lines.append(line)
        await update.message.reply_text("\n".join(lines))

    async def cmd_setmeta(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if len(context.args) < 2:
            await update.message.reply_text(
                "Usage : /setmeta <clé> <valeur>. Exemple: /setmeta gmail_address client@example.com"
            )
            return

        key = context.args[0]
        value = " ".join(context.args[1:])
        state = self._get_state(update.effective_chat.id)
        state.metadata[key] = value
        await update.message.reply_text(
            f"Métadonnée '{key}' enregistrée pour les prochaines réponses."
        )

    # ------------------------------------------------------------------
    # Messages utilisateurs
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.message
        if message is None or message.text is None:
            return

        state = self._get_state(update.effective_chat.id)
        state.history.append(
            ConversationMessage(role="user", content=message.text)
        )

        payload = CustomerPayload(
            channel=state.channel,
            customer_id=str(update.effective_user.id),
            thread_id=str(update.effective_chat.id),
            message=message.text,
            history=state.to_history(),
            metadata=dict(state.metadata),
        )

        reply = self.agent.handle_reply(payload)

        state.history.append(
            ConversationMessage(role="assistant", content=reply.reply)
        )

        await message.reply_text(reply.reply)

        if reply.actions:
            actions_text = "\n".join(f"• {action}" for action in reply.actions)
            await message.reply_text(
                f"Actions suggérées:\n{actions_text}",
                parse_mode=ParseMode.MARKDOWN if ParseMode else None,
            )

        delivery = reply.context.get("delivery") if isinstance(reply.context, dict) else None
        if isinstance(delivery, dict) and delivery.get("status") not in {None, "missing-handle"}:
            summary = delivery.get("status")
            connector = delivery.get("connector")
            await message.reply_text(
                f"Statut d'envoi via Composio: {summary} ({connector})"
            )

    # ------------------------------------------------------------------
    def _get_state(self, chat_id: int) -> SessionState:
        if chat_id not in self.sessions:
            self.sessions[chat_id] = SessionState()
        return self.sessions[chat_id]

    def run(self) -> None:
        """Démarre le bot en mode polling."""

        logger.info("Démarrage du bot Telegram pour l'agent client")
        self.application.run_polling()


def main() -> None:  # pragma: no cover - point d'entrée pratique
    settings = get_settings()
    token = settings.telegram_bot_token
    if not token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN n'est pas défini dans l'environnement."
        )

    bot = TelegramCustomerAgentBot(token=token, settings=settings)
    bot.run()


__all__ = ["TelegramCustomerAgentBot", "main"]


if __name__ == "__main__":  # pragma: no cover
    main()

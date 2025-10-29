# Infinity MCP Customer Service Agent

Ce dépôt contient un serveur [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) qui expose un agent IA de relation clientèle multicanal. L'agent combine un modèle de langage (ChatGPT via l'API OpenAI) et la plateforme d'orchestration Composio pour enrichir les réponses avec du contexte client.

## Fonctionnalités

- Support natif de WhatsApp, LinkedIn, Gmail, Outlook et Instagram via Composio.
- Intégration optionnelle avec Composio pour récupérer des connaissances et signaux client.
- Génération de réponses naturelles grâce aux modèles ChatGPT.
- API MCP simple (`/mcp/v1/execute`) pour piloter l'agent depuis différents connecteurs.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Configuration

Dupliquez le fichier `.env.example` en `.env` puis renseignez les clés API nécessaires :

```env
OPENAI_API_KEY="sk-..."
COMPOSIO_API_KEY="cmpo-..."
```

Les clés sont optionnelles : sans elles, le serveur fonctionne en mode simulation (réponses statiques et contexte synthétique), ce qui est utile pour le développement local.

## Démarrage du serveur

```bash
uvicorn mcp_customer_service.server:build_app --factory --host 0.0.0.0 --port 8000
```

### Endpoints principaux

- `GET /health` : vérifie l'état du serveur.
- `GET /mcp/v1/metadata` : décrit les capacités exposées.
- `POST /mcp/v1/execute` : exécute la commande `customer-agent.reply` avec une charge utile décrivant le message client.

Exemple de requête (conversation WhatsApp) :

```json
{
  "command": "customer-agent.reply",
  "payload": {
    "channel": "whatsapp",
    "customer_id": "12345",
    "message": "Je souhaite suivre ma commande",
    "history": [],
    "metadata": {
      "whatsapp_number": "+33600000000",
      "sentiment": "neutral",
      "urgency": "low"
    }
  }
}
```

### Métadonnées nécessaires par canal

Pour permettre à l'agent d'envoyer la réponse via Composio, fournissez l'identifiant adéquat dans `payload.metadata` :

| Canal | Clé(s) attendue(s) | Description |
| --- | --- | --- |
| `whatsapp` | `whatsapp_number` ou `phone_number` | Numéro international WhatsApp du client. |
| `linkedin` | `linkedin_profile` ou `profile_url` | URL du profil LinkedIn du client. |
| `gmail` | `gmail_address` ou `email` | Adresse Gmail du destinataire. |
| `outlook` | `outlook_address` ou `email` | Adresse Outlook/Exchange du destinataire. |
| `instagram` | `instagram_handle` ou `username` | Pseudonyme Instagram (sans `@`). |

Les canaux email (`gmail`, `outlook`) peuvent également inclure `subject` pour préciser l'objet du message.

### Vérifier l'accès aux connecteurs Composio

Pour confirmer que l'agent peut réellement envoyer des messages sur chaque canal, interrogez l'endpoint dédié :

```bash
curl http://localhost:8000/mcp/v1/connectors | jq
```

La réponse indique le mode (`live` ou `simulated`) et, pour chaque canal, si le connecteur et l'action Composio sont accessibles. Exemple de sortie :

```json
{
  "mode": "live",
  "connectors": [
    {
      "channel": "whatsapp",
      "connector": "whatsapp",
      "action": "send_message",
      "available": true
    },
    {
      "channel": "linkedin",
      "connector": "linkedin",
      "action": "send_message",
      "available": false,
      "reason": "Connecteur introuvable dans l'espace Composio"
    }
  ]
}
```

La même information est également exposée via `GET /mcp/v1/metadata` pour des vérifications rapides côté client MCP.

## Tests

Exécutez la suite depuis la racine du dépôt :

```bash
pytest
```

Sous Windows, l'équivalent est :

```powershell
py -m pytest
```

Les tests ne se contentent pas de vérifier que les modules se chargent : ils
simulent différentes réponses de l'API Composio pour confirmer que
`ComposioClient.list_available_tools()` signale correctement l'accès aux
connecteurs et aux actions attendus. Une fois la suite terminée, vous devez
obtenir un résumé `1 passed` ou `2 passed` selon les options activées, sans
erreurs.

## Tester l'agent en conditions réelles avec Telegram

Pour discuter avec l'agent et piloter les connexions Composio utilisateur par
utilisateur, vous pouvez lancer le bot Telegram inclus.

1. Créez un bot via [@BotFather](https://t.me/BotFather) et récupérez le jeton
   d'accès, puis renseignez la variable `TELEGRAM_BOT_TOKEN` dans votre fichier
   `.env`.
2. Installez les dépendances (voir section *Installation*) puis lancez le bot :

   ```bash
   python -m mcp_customer_service.telegram_bot
   ```

   ou créez un petit script :

   ```python
   from mcp_customer_service import TelegramCustomerAgentBot
   from mcp_customer_service.config import get_settings

   settings = get_settings()
   bot = TelegramCustomerAgentBot(token=settings.telegram_bot_token)
   bot.run()
   ```

3. Depuis Telegram, envoyez `/start` pour découvrir les commandes :
   - `/channel <canal>` pour choisir le canal simulé (WhatsApp, LinkedIn,
     Gmail, Outlook, Instagram).
   - `/connect <canal>` pour générer un lien Composio OAuth permettant à
     l'utilisateur de connecter son propre compte (Google, Meta, etc.).
   - `/installations` pour vérifier les connecteurs réellement associés au
     compte Composio de l'utilisateur.
   - `/setmeta <clé> <valeur>` pour fournir des identifiants précis (adresse
     email, numéro WhatsApp, profil LinkedIn…) utilisés lors de l'envoi.

Le bot réutilise exactement le même orchestrateur que l'API MCP : chaque
message envoyé depuis Telegram est transformé en `CustomerPayload`, passé au LLM
et, si les identifiants sont disponibles, la réponse est envoyée via Composio
sur le canal sélectionné. En absence de clés API ou de connecteurs installés,
le bot fonctionne en mode simulation et indique clairement l'état des
installations.

## Licence

MIT

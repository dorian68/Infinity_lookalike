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

```bash
pytest
```

## Licence

MIT

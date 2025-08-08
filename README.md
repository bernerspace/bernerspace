# Bernerspace

Unified, OAuth-enabled gateway for MCP tools. One server, one JWT, many integrations.

## Why

Integrating third‑party services into agentic systems is painful today:

- Most MCP servers lack OAuth capabilities, limiting user experience.
- Every MCP server requires separate deployment and management, increasing operational overhead.
- Each MCP server has different authentication layers, making unified integration nearly impossible.

## What You Get

- Single JWT across services via middleware (HS256, issuer/audience validated).
- OAuth middleware per integration (Slack live; more coming) with DB‑backed token storage.
- Consistent MCP tools interface for each service.
- Unified endpoints you can self‑host, e.g.:
  - <http://localhost:8000/mcp/slack>
  - <http://localhost:8000/mcp/gmail> (coming soon)

## How it works

1. Configure
   - Set up `CONFIG.json` with your service permissions.
1. Deploy
   - Self-host the unified MCP API platform.
1. Authenticate
   - OAuth middleware handles all service authentications.
1. Integrate
   - Use a single endpoint for all your AI agent integrations.

## Current Status

- Live integration: Slack
- Product name: Bernerspace

## Quickstart

1. Environment

Create a `.env` with the following variables:

```bash
JWT_SECRET=your-jwt-signing-secret
DATABASE_URL=postgresql://localhost:5432/mcp_server
CLIENT_ID=<slack_client_id>
CLIENT_SECRET=<slack_client_secret>
SLACK_REDIRECT_URI=http://localhost:8000/slack/oauth/callback
# Optional
CHANNEL_ID=<default_channel_id>
```

1. Install dependencies (choose one)

- Using pip
  - python -m venv .venv && source .venv/bin/activate
  - pip install -e .
- Using uv
  - uv venv && source .venv/bin/activate
  - uv pip install -e .

1. Run the server

- python server.py
- Server will listen on <http://localhost:8000>

1. Create a JWT to call the MCP server

- python generate_jwt.py --user-id <your_user_id>
- Use the printed token as: Authorization: Bearer `TOKEN`

## OAuth Flow (Slack)

- GET / returns `oauth_url` and instructions to authorize the workspace.
- Slack redirects to `SLACK_REDIRECT_URI` (defaults to `/slack/oauth/callback`).
- The server exchanges the code, enriches the token details, and persists it in Postgres.
- Tokens are stored in table `oauth_tokens` with composite key `(client_id, integration_type)` where `client_id` = your JWT subject (`sub`).

## Database

- Schema managed with Alembic (migrations included).
- Table: `oauth_tokens(client_id, integration_type, token_json, stored_at)`.
- Configure Postgres via `DATABASE_URL`.

## Available Tools (Slack)

- send_slack_message(channel, text, blocks?, attachments?, thread_ts?, username?, icon_emoji?, icon_url?)
  - Returns success metadata or an OAuth URL payload when authorization is required.
- update_slack_message(channel, message_ts, text?, blocks?, attachments?)
- get_oauth_url() – returns the provider OAuth URL for the current JWT subject.
- check_oauth_status() – reports whether an OAuth token exists for the JWT subject.

## MCP Client Configuration

Example client entry (mcp.json):

```json
{
  "servers": {
    "slack": {
      "url": "http://localhost:8000/mcp",
      "type": "http",
      "headers": {
        "Authorization": "Bearer YOUR_JWT"
      }
    }
  }
}
```

If the user hasn’t completed OAuth, tool calls will return an object with `requires_auth: true` and an `oauth_url` you can open to complete authorization.

## VS Code MCP Client Setup

Use this `mcp.json` in your VS Code user settings (replace `JWT` with your generated token):

```json
{
    "servers": {
        "slack": {
            "url": "http://localhost:8000/mcp",
            "type": "http",
              "headers": {
                "Authorization": "Bearer JWT"
        }
        }
    },
    "inputs": []
}
```

## LangChain Example

```python
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent

client = MultiServerMCPClient(
    {
        "slack": {
            "transport": "streamable_http",
            "url": "http://localhost:8000/mcp",
            "headers": {
                "Authorization": "Bearer YOUR_TOKEN"
            },
        }
    }
)

tools = await client.get_tools()
agent = create_react_agent("openai:gpt-4.1", tools)
response = await agent.ainvoke({"messages": "what is the weather in nyc?"})
```

## Unified Service Configuration

Provide a single `CONFIG.json` to declare scopes and required env for each service (concept):

```json
{
  "slack": {
    "permission": "chat:write,channels:read,groups:read,im:read,mpim:read",
    "env": [
      "CLIENT_ID",
      "CLIENT_SECRET",
      "SLACK_REDIRECT_URI"
    ]
  }
}
```

## Endpoints

- GET / – service info + OAuth URL (Slack)
- GET /health – health/status
- GET /slack/oauth/callback – OAuth callback that persists tokens and associates them with the JWT subject
- MCP tools served at /mcp via FastMCP

## Roadmap

- Gmail, Google Drive, GitHub and more providers
- Centralized policy enforcement (scopes/roles per JWT)
- Admin UI for managing connections and tokens

## Notes

- Keep your `.env` secrets secure; never commit them.
- The server validates JWT `iss` and `aud`. Defaults: issuer `bernerspace-ecosystem`, audience `mcp-slack-server`.

— Bernerspace
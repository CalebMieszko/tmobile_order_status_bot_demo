# Order Status Chatbot

Minimal FastAPI backend that simulates an order-status chatbot. Loads a CSV as an in-memory DB, uses OpenAI function calling when an API key is present, and a deterministic mock when it is not.

## Notes
- Smoke test instructions below.
- For convenience' sake, I've included poetry and tools for testing, linting, and formatting to allow for fast, easy setup.
- This is configured as a module (order_status_bot). In prod we might adjust the file structure, nesting the module in a sys directory.
- If `OPENAI_API_KEY` is unset, the app runs in a deterministic mock mode.
- Only `processing` orders can be canceled. `shipped` and `canceled` are immutable to reflect real-world policies.
- Conversation state and order overrides are in memory only for this example.

## Requirements
- Python 3.11
- Poetry
- Project dependencies are defined in [pyproject.toml](./pyproject.toml)

## Setup
```
poetry install --with dev         
cp .env.example .env
```

## Run
```
poetry run uvicorn order_status_bot.app:app --reload
```
App will listen on http://127.0.0.1:8000


## Endpoints
- POST `/conversations` → `{ "conversation_id": "<uuid>" }`
- GET `/conversations/{conversation_id}/messages` → list of user and assistant messages
- POST `/conversations/{conversation_id}/messages` → `{ "assistant": {...}, "tool_result": {...}? }`

## Quick smoke test
### create conversation
```
CID=$(curl -s -X POST http://127.0.0.1:8000/conversations | python -c "import sys,json;print(json.load(sys.stdin)['conversation_id'])")
```

### check order 12345
```
curl -s -X POST http://127.0.0.1:8000/conversations/$CID/messages -H "Content-Type: application/json" -d '{"content":"check order 12345"}'
```

### cancel order 23456
```
curl -s -X POST http://127.0.0.1:8000/conversations/$CID/messages -H "Content-Type: application/json" -d '{"content":"cancel order 23456"}'
```

### verify status
```
curl -s -X POST http://127.0.0.1:8000/conversations/$CID/messages -H "Content-Type: application/json" -d '{"content":"check order 23456"}'
```

## Test
```
poetry run pytest -q
```

## Lint and format
```
poetry run ruff check .
poetry run black --check .
```
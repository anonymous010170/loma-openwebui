## LoMA-Agent

Technical assistant built on the Agno framework. LoMA routes user queries to specialized agents that answer questions about machine alarms, troubleshooting, and procedural manuals using RAG and file search.

## Architecture

LoMA is a multi-agent team with a **router** and two specialist agents:

- **LoMA Router** (`Team`) — Detects the user's intent and language, then delegates to the appropriate specialist.
- **Alarm Specialist** (`Agent`) — Looks up alarm codes by searching files on disk using file tools (read, search, list).
- **Manuals Specialist** (`Agent`) — Answers procedural and specification questions via RAG against a Qdrant vector store populated from a JSONL knowledge base.

```
User query
  └─► LoMA Router ──► Alarm Specialist [FS Agent]
        └─► Manuals Specialist [RAG]
```

## Stack

| Component | Technology |
|-----------|------------|
| Agent framework | [Agno](https://github.com/agno-agi/agno) |
| LLM | Ollama (configurable via `LOMA_MODEL` and `ROUTER_MODEL`) |
| Embeddings | Ollama `nomic-embed-text` |
| Vector DB | Qdrant |
| File search | Local filesystem (`/app/kb`) |
| Observability | PostgreSQL (`agent_logs` table) |
| API | FastAPI + SSE streaming |

## API

### Run agent

```
POST /v1/agents/{agent_id}/runs
```

**Body:**
```json
{
  "message": "What does A0001 mean?",
  "stream": true,
  "session_id": "optional-session-id",
  "user_id": "optional-user-id"
}
```

Returns an SSE stream with `content`, `tool`, and `citations` events. Non-streaming mode returns a single JSON object.

## Knowledge base

Populate the KB by providing a JSONL file at `/app/data/dataset.jsonl`. Each line:

```jsonl
{"text": "...", "metadata": {"file_path": "/machine/language/file.txt"}}
```

Directories are expected as `/Machine/Language/Filename`. The knowledge loader extracts `machine`, `language`, and `type` (`Alarms` or `Manuals`) from the path and indexes only `Manuals` into Qdrant.

## Project structure

```
main.py          # FastAPI app, SSE streaming, API endpoints
agents.py        # Agent/Team construction, logging hooks
kb_loader.py     # JSONL parsing, Qdrant RAG knowledge base
logger.py        # PostgreSQL logging (agent_logs table)
instructions.py  # Agent system prompts and tool instructions
requirements.txt # Python dependencies
Dockerfile       # Container image
```

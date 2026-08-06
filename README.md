## LoMA-OpenWebUI

**LoMA-OpenWebUI** is a production-ready local AI ecosystem. It integrates [Open WebUI](https://github.com/open-webui/open-webui) with a custom **LoMA-Agent** via a dynamic pipeline system, providing an interface for local LLMs, agents, and session logging.

## Structure

```text
loma-openwebui/
├── loma_agent/            # Core Agent logic (FastAPI)
│   ├── agents.py          # Agent definitions
│   ├── instructions.py    # Agent instructions
│   ├── kb_loader.py       # Knowledge base utilities
│   ├── logger.py          # Database logging logic
│   ├── main.py            # API Entry point
│   └── Dockerfile
├── ollama/                # Local LLM management
│   ├── Modelfile          # Model configuration
│   ├── entrypoint.sh      # Setup script
│   └── Dockerfile
├── eval/                  # Agent evaluation
│   └── eval.py            # Evaluation script
├── pipelines/             # OpenWebUI Pipeline Bridge
│   ├── pipelines_custom/  # OpenWebUI Pipelines here
│   │   └── loma_pipeline.py
│   ├── build.sh
│   └── Dockerfile
├── kb/                    # Plain text knowledge base for FS navigation
├── models/                # Local .gguf files (Ollama)
├── data/                  # RAG Dataset (dataset.jsonl)
├── .env                   # Environment variables
├── docker-compose.yml     # Main services
├── docker-compose-gpu.yml # GPU Acceleration override
└── Makefile               # Shortcuts for common tasks

```

### Services Architecture
- `open-webui`: The frontend interface for chatting with the agent.
- `pipelines`: Automatically detects and attaches custom logic from pipelines_custom/ to OpenWebUI.
- `agno-agent-api`: A FastAPI server orchestration the Agent's reasoning and tools.
- `ollama`: Handles local LLM inference.
- `qdrant`: High-performance Vector Database for RAG.
- `postgres-agno`: Persistent storage for agent session logs and history.

### Prerequisites

Clone the repository and prepare the following:

1. Environment: Create a .env file (see the [Environment Variables](#environment-variables) section).
2. Models: Where `.gguf` files must be placed.
3. Knowledge Base:
    - Place raw documents in `data/` as `dataset.jsonl`.
    - Generate the plain text KB for the agent using `create_plain_kb` method of `kb_loader.py`.

### Installation and Execution

Using `Makefile`:

- GPU Mode:
    ```bash
        make gpu
    ```
- CPU Mode:
    ```bash
        make build
    ```
- Start without rebuilding:
    ```bash
        make up
    ```

Using Docker Compose directly:

- GPU Mode:
    ```bash
        docker compose -f docker-compose.yml -f docker-compose-gpu.yml up -d --build
    ```
- CPU Mode:
    ```bash
        docker compose up --build -d
    ```

### Environment Variables

The `.env` file should contain at least the following environment variables:

```env
    # Postgres Configuration
    POSTGRES_USR=your_user
    POSTGRES_PWD=your_password
    POSTGRES_PORT=5432

    # Ollama and Models
    OLLAMA_PORT=11434
    LOMA_MODEL=loma
    EMBEDDING_MODEL=nomic-embed-text:latest

    # Qdrant and Agno External Ports
    AGNO_PORT=8000
    QDRANT_PORT=6333

    # Pipelines
    PIPELINES_PORT=9099
    PIPELINES_API_KEY=0p3n-w3bu!
    
    # OpenWebUI Configuration
    OPENWEBUI_PORT=3000
```

## Notes

- **Dynamic Pipelines**: Any new script added to `pipelines/pipelines_custom/` will be automatically loaded when the container starts.
- **Persistence**: Database logs are stored in the `postgres-loma` docker volume, ensuring history is kept across restarts.
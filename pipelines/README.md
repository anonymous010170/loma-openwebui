## Open-WebUI Pipelines

Custom OpenWebUI Pipeline that integrates [Agno framework](https://github.com/agno-agi/agno) agents as selectable models in OpenWebUI.

## Overview

This pipeline dynamically discovers Agno agents from the Agno API and exposes them as models within OpenWebUI. It supports streaming responses, citations, tool calls, and session-based continuity.

## Structure

```
pipelines/
├── Dockerfile                 # Builds a custom pipelines image
├── build.sh                   # Auto-discovers .py pipeline files and builds the image
└── pipelines-custom/
    ├── loma_pipeline.py       # Main pipeline: agent discovery + execution
    └── requirements.txt       # Python dependencies
```

## Pipeline Features

- **Dynamic Agent Discovery** - Fetches available agents from the Agno API and registers them as models
- **Streaming** - Streams agent responses in real-time via SSE
- **Citations** - Handles and surfaces agent citations (source, machine, content)
- **Tool Call Events** - Emits status events for each tool invocation by the agent
- **Session Management** - Uses OpenWebUI chat ID for session continuity across conversations

## Adding Custom Pipelines

Place additional `.py` files in `pipelines-custom/`. The `build.sh` script will auto-detect them and include them in the image.

## Ollama

Docker image for running an Ollama server with LoMA model loaded.

## Description

This container runs an Ollama server with a custom-trained GGUF model tuned for technical Q&A.
The `entrypoint.sh` script automatically creates the model from the GGUF file if `LOMA_MODEL` is not already loaded in Ollama, and pulls the configured embedding model.

## Environment Variables

| Variable | Description |
|---|---|
| `LOMA_MODEL` | Name and tag for the custom model |
| `ROUTER_MODEL` | Router model to pull and make available |
| `EMBEDDING_MODEL` | Embedding model to pull and make available |

## Change Model

If you want to change the fine-tuned model or the embedding model after you've already loaded it, run:

```
    docker exec -it ollama ollama rm <model-name>
```

And then restart the container, the `entrypoint.sh` file will load the new model autonomously (remember to change the `FROM` in the Modelfile with the new `GGUF`).
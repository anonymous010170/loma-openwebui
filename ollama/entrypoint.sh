#!/bin/bash

ollama serve &
OLLAMA_PID=$!

until ollama list > /dev/null 2>&1; do
    sleep 1
done

if ! ollama list | grep -q "${LOMA_MODEL%:*}"; then
    echo "Creating custom model ${LOMA_MODEL}..."
    ollama create "$LOMA_MODEL" -f /Modelfile
fi

if ! ollama list | grep -q "$ROUTER_MODEL"; then
    echo "Pulling router model ${ROUTER_MODEL}..."
    ollama pull "$EMBEDDING_MODEL"
fi

if ! ollama list | grep -q "$EMBEDDING_MODEL"; then
    echo "Pulling embedding model ${EMBEDDING_MODEL}..."
    ollama pull "$EMBEDDING_MODEL"
fi

ollama run ${ROUTER_MODEL} "hi" > /dev/null 2>&1
ollama run ${LOMA_MODEL} "hi" > /dev/null 2>&1
wait $OLLAMA_PID
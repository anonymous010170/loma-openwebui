#!/bin/bash

set -e

# build in the specific pipelines
PIPELINE_DIR="pipelines-custom"
# assuming the above directory is in your source repo and not skipped by `.dockerignore`, it will get copied to the image
PIPELINE_PREFIX="file:///app"

# retrieve all the sub files
export PIPELINES_URLS=
for file in "$PIPELINE_DIR"/*; do
    if [[ -f "$file" ]]; then
        if [[ "$file" == *.py ]]; then
            if [ -z "$PIPELINES_URLS" ]; then
                PIPELINES_URLS="$PIPELINE_PREFIX/$file"
            else
                PIPELINES_URLS="$PIPELINES_URLS;$PIPELINE_PREFIX/$file"
            fi
        fi
    fi
done
echo "New Custom Install Pipes: $PIPELINES_URLS"

docker build --build-arg PIPELINES_URLS=$PIPELINES_URLS --build-arg MINIMUM_BUILD=true -f Dockerfile .
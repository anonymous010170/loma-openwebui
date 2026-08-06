FROM ghcr.io/open-webui/pipelines:main

COPY pipelines-custom/ /app/pipelines
RUN pip install -r /app/pipelines/requirements.txt

ENV PIPELINES_URL="file:///app/pipelines-custom/loma_pipeline.py"
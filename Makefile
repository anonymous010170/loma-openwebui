up:
	docker compose up -d

build:
	docker compose up --build -d

gpu:
	docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build

down:
	docker compose down

test:
	docker exec -it agno-agent-api-1 python3 /app/eval/eval.py --file $(INPUT_FILE) --column $(EVAL_COLUMN) --output $(OUTPUT_FILE)
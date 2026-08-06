import os
import json
import threading

from datetime import datetime, timezone
from agno.models.ollama import Ollama
from pathlib import Path
from agno.agent import Agent
from agno.tools.file import FileTools
from agno.tools.mem0 import Mem0Tools
from agno.team import Team, TeamMode
from agno.agent import RunOutput
from kb_loader import KnowledgeBaseLoMA
from logger import Logger
from instructions import (
    alarms_description,
    alarms_instructions,
    manuals_instructions,
    team_instructions
)

class Agents:
    def __init__(
        self,
        model_name: str = None,
        router_name: str = None,
        qdrant_host: str = None,
        qdrant_port: str = None,
        ollama_host: str = None,
        ollama_port: str = None,
        embedding_model: str = None,
        embedding_dims: int = None,
        postgres_url: str = None
    ):
        self.model_name = model_name or os.getenv("LOMA_MODEL")
        self.router_name = router_name or os.getenv("ROUTER_MODEL")
        self.qdrant_host = qdrant_host or os.getenv("QDRANT_HOST")
        self.qdrant_port = qdrant_port or os.getenv("QDRANT_PORT")
        ollama_host = ollama_host or os.getenv("OLLAMA_HOST")
        ollama_port = ollama_port or os.getenv("OLLAMA_PORT")
        self.qdrant_url = f"http://{self.qdrant_host}:{self.qdrant_port}"
        self.ollama_url = f"http://{ollama_host}:{ollama_port}"
        self.embedding_model = embedding_model or os.getenv("EMBEDDING_MODEL")
        self.embedding_dims = embedding_dims or os.getenv("EMBEDDING_DIMS")
        postgres_url = postgres_url or os.getenv("POSTGRES_URL")
        self.logger = Logger(postgres_url=postgres_url)

        self.team_model = Ollama(
            id=self.router_name,
            host=self.ollama_url,
            options={
                "temperature": 0.0,
                "num_ctx": 8192
            }    
        )

        self.agent_model = Ollama(
            id=self.model_name,
            host=self.ollama_url,
            options={
                "temperature": 0.3,
                "num_ctx": 8192
            }    
        )

        kb_loma = KnowledgeBaseLoMA(
            model=self.model_name,
            path_json="/app/data/dataset.jsonl",
            collection_name="loma-rag-manuals-1",
            qdrant_url=self.qdrant_url, 
            ollama_url=self.ollama_url
        )
        threading.Thread(target=kb_loma.populate_kb, daemon=True).start()
        self.kb = kb_loma.load_kb(
            max_results=5
        )

        self.fs_path = Path("/app/kb") 
        
        self.file_tools = FileTools(
            base_dir=self.fs_path,
            enable_read_file=True,
            enable_search_content=True,
            enable_list_files=True,
            enable_save_file=False,
        )

        self.mem0_config = {
            "llm": {
                "provider": "ollama",
                "config": {
                    "model": self.model_name,
                    "ollama_base_url": self.ollama_url
                }
            },
            "embedder": {
                "provider": "ollama",
                "config": {
                    "model": "nomic-embed-text",
                    "ollama_base_url": self.ollama_url
                }
            },
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "collection_name": "memory_loma",
                    "host": self.qdrant_host,
                    "port": self.qdrant_port,
                    "embedding_model_dims": self.embedding_dims
                }
            }
        }

        self._alarms_agent = self._build_alarms_agent()
        self._manuals_agent = self._build_manuals_agent()
        self._team = self._build_team()

    def _logging(self, run_output: RunOutput):
        messages = run_output.messages or []
        last_message = messages[-1] if messages else None

        metrics_obj = getattr(last_message, "metrics", None)
        metrics = metrics_obj.__dict__ if hasattr(metrics_obj, "__dict__") else None

        references = []
        if run_output.references:
            for r in run_output.references:
                for ref in getattr(r, "references", []) or []:
                    references.append({
                        "source": ref.get("name"),
                        "machine": ref.get("meta", {}).get("machine"),
                        "content":ref.get("content", "")
                    })

        self.logger.log(
            timestamp=datetime.now(timezone.utc),
            run_id=run_output.run_id,
            agent_name=run_output.agent_name,
            query=getattr(getattr(run_output, "input", None), "input_content", None),
            response=getattr(run_output, "content", None),
            model=run_output.model,
            provider=run_output.model_provider,
            metrics=json.dumps(metrics, default=str) if metrics else None,
            log_references=json.dumps(references, default=str)
        )

    def _build_alarms_agent(self):
        return Agent(
            name="Alarm Specialist",
            role="Agent that answer questions about alarm codes (e.g., ALM03346, Error 504, A123).",
            model=self.agent_model,
            tools=[self.file_tools],
            description=alarms_description,
            instructions=alarms_instructions,
            stream=True,
            stream_events=True,
            markdown=True,
            post_hooks=[self._logging]
        )
    
    def _build_manuals_agent(self):
        return Agent(
            name="Manuals Specialist",
            role="Agent that answer general or procedural questions.",
            model=self.agent_model,
            knowledge=self.kb,
            search_knowledge=True,
            instructions=manuals_instructions,
            tool_call_limit=2,
            enable_agentic_knowledge_filters=True,
            stream=True,
            stream_events=True,
            markdown=True,
            post_hooks=[self._logging]
        )
    
    def _build_team(self):
        return Team(
            name="LoMA Router",
            model=self.team_model,
            members=[self._alarms_agent, self._manuals_agent],
            mode=TeamMode.route,
            respond_directly=True,
            instructions=team_instructions,
            determine_input_for_members=False,
            stream_member_events=True,
            stream_events=True,
            share_member_interactions=False,
            show_members_responses=True,
        )
    
    def get_team_agent(self):
        return self._team
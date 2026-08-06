"""
OpenWebUI Pipe for Agno Framework Integration

This pipe integrates Agno framework agents as selectable models in OpenWebUI.
It provides dynamic agent discovery and execution capabilities.
"""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Union, AsyncGenerator, Callable, Awaitable
import os
import requests
import json
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Pipeline:
    class Valves(BaseModel):
        AGNO_API_BASE_URL: str = Field(
            default="http://agno-agent-api-1:8000/v1",
            description="Base URL for the Agno framework API endpoints."
        )
        API_KEY: str = Field(
            default="",
            description="Optional API key for authentication with Agno API."
        )
        MODEL_PREFIX: str = Field(
            default="AGNO/",
            description="Prefix to be added before agent names in OpenWebUI."
        )
        DEFAULT_MODEL: str = Field(
            default=os.getenv("LOMA_MODEL"),
            description="Default Ollama model to use for agent execution."
        )
        STREAM_RESPONSES: bool = Field(
            default=True,
            description="Enable streaming responses from agents."
        )
        REQUEST_TIMEOUT: int = Field(
            default=300,
            description="Timeout in seconds for API requests."
        )
        DEBUG_MODE: bool = Field(
            default=True,
            description="Enable debug logging for troubleshooting."
        )

    def __init__(self):
        self.valves = self.Valves()
        self.name = "Agentic-LoMA"

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        if self.valves.API_KEY:
            headers["Authorization"] = f"Bearer {self.valves.API_KEY}"
        return headers

    def _log_debug(self, message: str, data: Optional[Dict] = None):
        """Log debug information if debug mode is enabled."""
        if self.valves.DEBUG_MODE:
            if data:
                logger.info(f"[AGNO-PIPE DEBUG] {message}: {json.dumps(data, indent=2)}")
            else:
                logger.info(f"[AGNO-PIPE DEBUG] {message}")

    def _extract_agent_id(self, model_name: str) -> str:
        """Extract agent ID from the model name."""
        if model_name.startswith(self.valves.MODEL_PREFIX):
            return model_name[len(self.valves.MODEL_PREFIX):]
        return model_name
    
    def _extract_event_info(self, event_emitter) -> tuple[Optional[str], Optional[str]]:
        if not event_emitter or not event_emitter.__closure__:
            return None, None
        for cell in event_emitter.__closure__:
            if isinstance(request_info := cell.cell_contents, dict):
                chat_id = request_info.get("chat_id")
                message_id = request_info.get("message_id")
                return chat_id, message_id
        return None, None

    def _get_last_user_message(self, messages: List[Dict]) -> str:
        """Extract the last user message from the conversation."""
        for message in reversed(messages):
            if message.get("role") == "user":
                return message.get("content", "")
        return ""
    
    def _emit_event(self, type: str, data: dict):
        return {
            "event": {
                "type": type,
                "data": data
            }
        }
    
    def _handle_citations(self, data: dict):
        for citation in data.get("citations", []):
            name = citation.get("source", {}).get("name", "source")
            machine = citation.get("metadata", [{}])[0].get("machine", "")
            document_content = citation.get("document", [""])[0]

            document = f"**Source** \n{name}\n\n**Machine**\n{machine}\n\n**Content**\n{document_content}"
            yield self._emit_event("citation", {"document": [document], "metadata": [{"source": name, "machine": machine}], "source": {"name": name}})

    def _handle_tool_calls(self, data: dict):
        data_tool = data['tool']
        yield self._emit_event("status", {"description": f"Agent {data_tool['agent']} called tool {data_tool['tool_name']}.", "done": False})

        for filter, value in data_tool['filters'].items():
            yield self._emit_event("status", {"description": f"Filtering by {filter}: {value}", "done": False})

    def pipes(self) -> List[Dict[str, str]]:
        """
        Fetch available agents from Agno API and return them as OpenWebUI models.
        
        Returns:
            List of dictionaries with 'id' and 'name' keys for each available agent.
        """
        try:
            self._log_debug("Fetching available agents from Agno API")
            
            # Make request to get available agents
            response = requests.get(
                f"{self.valves.AGNO_API_BASE_URL}/agents",
                headers=self._get_headers(),
                timeout=self.valves.REQUEST_TIMEOUT
            )
            
            if response.status_code == 200:
                agents = response.json()
                self._log_debug("Successfully fetched agents", {"agents": agents})
                
                # Transform agents into OpenWebUI model format
                models = []
                for agent_id in agents:
                    description = f"Agno {agent_id.replace('_', ' ').title()}"
                    models.append({
                        "id": agent_id,
                        "name": f"{self.valves.MODEL_PREFIX}{description}"
                    })
                
                self._log_debug("Transformed agents to models", {"models": models})
                return models
                
            else:
                error_msg = f"Failed to fetch agents. Status: {response.status_code}"
                self._log_debug(error_msg, {"response": response.text})
                # Return empty model in case of error
                return []
                
        except requests.exceptions.ConnectionError:
            error_msg = f"Cannot connect to Agno API at {self.valves.AGNO_API_BASE_URL}"
            self._log_debug(error_msg)
            return [{
                "id": "connection_error",
                "name": f"Connection Error: {error_msg}"
            }]
            
        except requests.exceptions.Timeout:
            error_msg = "Request timeout while fetching agents"
            self._log_debug(error_msg)
            return [{
                "id": "timeout_error",
                "name": f"Timeout Error: {error_msg}"
            }]
            
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self._log_debug(error_msg)
            return [{
                "id": "general_error",
                "name": f"Error: {error_msg}"
            }]

    def pipe(
        self,
        user_message: str,
        model_id: str,  
        messages: List[Dict],
        body: Dict,
        __user__: Optional[Dict] = None,
        __event_emitter__: Callable[[dict], Awaitable[None]] = None,
        __event_call__: Callable[[dict], Awaitable[dict]] = None
    ) -> Union[str, AsyncGenerator]:
        """
        Execute the selected Agno agent with the user's message.
        
        Args:
            body: Request body from OpenWebUI containing messages, model, etc.
            __user__: User information from OpenWebUI
            
        Returns:
            Agent response (streaming or complete)
        """

        try:
            self._log_debug("Processing pipe request", {"body": body, "user": __user__})
            
            # Extract agent ID from model name
            # model_name = body.get("model", "")
            # function name is appended to the model id in OpenWebUI
            # agent_id = self._extract_agent_id(model_name).split(".")[1]
            agent_id = model_id.split(".")[-1] if "." in model_id else model_id
            
            # Extract user message from conversation
            # messages = body.get("messages", [])
            # user_message = self._get_last_user_message(messages)
            
            if not user_message:
                return "Error: No user message found in the conversation."

            # Prepare request payload for Agno API
            payload = {
                "message": user_message,
                "stream": self.valves.STREAM_RESPONSES and body.get("stream", True),
                "model": self.valves.DEFAULT_MODEL
            }

            # Add user context if available
            payload["user_id"] = body.get("user", {}).get("id", "")

            # Use OpenWebUI's chat ID as session ID for continuity across chats
            # If chat_id is not available, fall back to user ID and timestamp
            chat_id, _ = self._extract_event_info(__event_emitter__)

            if not chat_id:
                chat_id = f"{payload['user_id']}_{datetime.now().strftime('%Y%m%d%H%M%S')}" # Added H, M, S for more granularity if chat_id is missing

            payload["session_id"] = chat_id
            
            self._log_debug("Sending request to Agno agent", {
                "agent_id": agent_id,
                "payload": payload
            })
            
            # Make request to Agno agent
            response = requests.post(
                f"{self.valves.AGNO_API_BASE_URL}/agents/{agent_id}/runs",
                json=payload,
                headers=self._get_headers(),
                timeout=self.valves.REQUEST_TIMEOUT,
                stream=payload["stream"]
            )
            
            if response.status_code == 200:
                if payload["stream"]:
                    # Return streaming response
                    yield from self._stream_response(response)
                else:
                    # Return complete response
                    result = response.json()
                    self._log_debug("Received complete response", {"result": result})
                    return result
            else:
                error_msg = f"Agent execution failed. Status: {response.status_code}"
                self._log_debug(error_msg, {"response": response.text})
                return f"Error: {error_msg}"
                
        except requests.exceptions.ConnectionError:
            error_msg = f"Cannot connect to Agno API at {self.valves.AGNO_API_BASE_URL}"
            self._log_debug(error_msg)
            return f"Connection Error: {error_msg}"
            
        except requests.exceptions.Timeout:
            error_msg = "Request timeout while executing agent"
            self._log_debug(error_msg)
            return f"Timeout Error: {error_msg}"
            
        except Exception as e:
            error_msg = f"Unexpected error during agent execution: {str(e)}"
            self._log_debug(error_msg)
            return f"Error: {error_msg}"

    def _stream_response(self, response):
        """
        Stream the response from Agno agent.
        
        Args:
            response: Streaming response from requests
            
        Yields:
            Response chunks
        """
        yield self._emit_event("status", {"description": "Starting LoMA Agent...", "done": False})
        try:
            first_chunk = True
            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)

                        if "citations" in data:
                            yield from self._handle_citations(data)
                            continue
                        elif "tool" in data:
                            yield from self._handle_tool_calls(data)
                            continue
                        else:
                            if first_chunk:
                                yield self._emit_event("status", {"description": "Generating...", "done": False})
                                first_chunk = False
                            yield line
                    except json.JSONDecodeError:
                        yield line
                else:
                    yield line
        except Exception as e:
            error_msg = f"Error during streaming: {str(e)}"
            self._log_debug(error_msg)
            yield f"Error: {error_msg}"
        finally:
            yield self._emit_event("status", {"description": "Generation completed.", "done": True})
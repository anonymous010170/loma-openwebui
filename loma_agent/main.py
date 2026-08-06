import os
import uvicorn
import json

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, Iterator
from agno.agent import RunOutputEvent, RunEvent
from agno.team import TeamRunEvent
from agents import Agents

app = FastAPI()
agents = Agents()

class ChatRequest(BaseModel):
    message: str
    stream: bool = True
    session_id: Optional[str] = None
    user_id: Optional[str] = None

def format_sse(data: dict):
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
    
def handle_tool_call(chunk):
    tool_args = chunk.tool.tool_args or {}
    filters = tool_args.get("filters") or []

    agent_name = getattr(chunk, "agent_name", None) or getattr(chunk, "team_name", None) or "Unknown"

    return format_sse({"tool": {
        "agent": agent_name,
        "tool_name": chunk.tool.tool_name,
        "filters": {
            filter['key']: filter['value']
            for filter in filters
            if isinstance(filter, dict) and "key" in filter and "value" in filter
        }
    }})

def handle_content(chunk):
    if chunk.content is None:
        return None

    return format_sse({
        "choices": [{
            "delta": {"content": chunk.content},
            "finish_reason": None
        }]
    })

def handle_citations(chunk):
    if not chunk.tool or not chunk.tool.result:
        return None
    citations = []
    try:
        tools = json.loads(chunk.tool.result)
        if isinstance(tools, dict):
            if not tools.get("matches_found"):
                return None
            for ref in tools['files']:
                if not isinstance(ref, dict):
                    continue
                citations.append({
                    "document": [ref.get("snippet", "")],
                    "metadata": [{"source": ref.get("file", "")}],
                    "source": {"name": ref.get("file", "")}
                })
        elif isinstance(tools, list):
            for ref in tools:
                if not isinstance(ref, dict):
                    continue
                citations.append({
                    "document": [ref.get("content", "")],
                    "metadata": [{"source": ref.get("name", "")}],
                    "source": {"name": ref.get("name", "")}
                })
        return format_sse({"citations": citations}) if citations else None
    except (json.JSONDecodeError, TypeError):
        return None

def get_event_handler():
    return {
        TeamRunEvent.run_content: handle_content,
        TeamRunEvent.tool_call_started: handle_tool_call,
        TeamRunEvent.tool_call_completed: handle_citations,
        RunEvent.tool_call_started: handle_tool_call,
        RunEvent.tool_call_completed: handle_citations
    }

async def stream_agno_response(agent, message: str, user_id: str, session_id: str):
    try:
        event_handler = get_event_handler()
        async for chunk in agent.arun(
            message, 
            stream=True,
            stream_events=True,
            stream_member_events=True,
            user_id=user_id, 
            session_id=session_id,
        ):
            handler = event_handler.get(chunk.event, None)            
            if handler:
                result = handler(chunk)
                if result:
                    yield result
            
    except Exception as e:
        yield format_sse({
            "choices": [{
                "delta": {"content": f"\n\nError: {str(e)}"},
                "finish_reason": "stop"
            }]
        })
    finally:
        yield format_sse({
            "choices": [{
                "delta": {},
                "finish_reason": "stop"
            }]
        })
        yield "data: [DONE]\n\n"

@app.get("/v1/agents")
async def list_agents():
    return ["loma"]

@app.post("/v1/agents/{agent_id}/runs")
async def run_agent(agent_id: str, request: ChatRequest):
    target_agent = agents.get_team_agent()
    
    if not target_agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    if request.stream:
        return StreamingResponse(
            stream_agno_response(
                target_agent, 
                request.message, 
                request.user_id, 
                request.session_id
            ),
            media_type="text/event-stream"
        )
    else:
        response = await target_agent.arun(
            request.message,
            session_id=request.session_id,
            user_id=request.user_id
        )
        return {"choices": [{"message": {"content": response.content}}]}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
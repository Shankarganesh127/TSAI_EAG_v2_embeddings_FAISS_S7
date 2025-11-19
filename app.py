import os
import asyncio
import json
import shutil
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from search_agent import SearchAgent
import uvicorn

app = FastAPI()

# Mount static files
ROOT = Path(__file__).parent.resolve()
STATIC_DIR = ROOT / "static"
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Store active connections
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        try:
            await websocket.send_text(message)
        except RuntimeError:
            print("WebSocket connection closed, cannot send message.")

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

# Agent instance (per session or global? For simplicity, one global agent for now, 
# but ideally should be per websocket session. Let's do per websocket.)
agents = {}

@app.get("/")
async def get():
    return FileResponse(str(STATIC_DIR / "index.html"))

@app.get("/download")
async def download_resources():
    """Generate and download a formatted report with all collected data."""
    import datetime
    
    documents_path = ROOT / "documents"
    zip_path = ROOT / "search_agent_data"
    
    # Create a temporary directory to organize the download
    temp_dir = ROOT / "temp_download"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir()
    
    # Generate a summary report
    report_lines = []
    report_lines.append("# Search Agent Report")
    report_lines.append(f"\nGenerated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Try to get agent data if available
    if agents:
        # Get the most recent agent
        agent = list(agents.values())[-1] if agents else None
        
        if agent:
            # Add topic
            if agent.current_topic:
                report_lines.append(f"## Topic\n\n{agent.current_topic}\n")
            
            # Add conversation history
            report_lines.append("## Conversation History\n")
            for item in agent.history:
                if item['role'] == 'user':
                    report_lines.append(f"\n**User:** {item['content']}\n")
                elif item['role'] == 'assistant':
                    report_lines.append(f"\n**Assistant:** {item['content']}\n")
            
            # Extract and organize links from memory
            report_lines.append("\n## Collected Resources\n")
            links_found = set()
            
            for memory_item in agent.memory.data:
                text = memory_item.text
                # Extract URLs from memory items
                import re
                urls = re.findall(r'https?://[^\s\]]+', text)
                for url in urls:
                    if url not in links_found:
                        links_found.add(url)
                        # Try to extract title if available
                        title_match = re.search(r'Title:\s*([^\n]+)', text)
                        if title_match:
                            report_lines.append(f"- [{title_match.group(1).strip()}]({url})")
                        else:
                            report_lines.append(f"- {url}")
    
    # Save the report
    report_content = "\n".join(report_lines)
    (temp_dir / "REPORT.md").write_text(report_content, encoding='utf-8')
    
    # Copy documents if they exist
    if documents_path.exists():
        shutil.copytree(documents_path, temp_dir / "documents")
    
    # Create zip
    shutil.make_archive(str(zip_path), 'zip', temp_dir)
    
    # Cleanup
    shutil.rmtree(temp_dir)
    
    return FileResponse(f"{zip_path}.zip", filename="search_agent_data.zip")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    
    # Callback to send updates to UI
    def agent_callback(event_type: str, data: any):
        asyncio.create_task(manager.send_personal_message(json.dumps({
            "type": event_type,
            "data": data
        }), websocket))

    # Initialize agent for this connection
    agent = SearchAgent(callback=agent_callback)
    agents[websocket] = agent
    
    # Start agent loop in background
    agent_task = asyncio.create_task(agent.run())

    try:
        while True:
            data = await websocket.receive_text()
            # Send input to agent
            await agent.input_queue.put(data)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await agent.input_queue.put("EXIT")
        await agent_task
        del agents[websocket]
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)

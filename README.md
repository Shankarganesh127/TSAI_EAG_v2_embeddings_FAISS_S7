# Search Agent V2

## Overview
A lightweight AI‑driven search assistant that runs in a browser UI. It processes a user query through four cognitive layers (Perception → Memory → Decision → Action), uses a local FAISS vector store for fast retrieval, and can call external tools via the MCP server.

## Project Structure
| File / Directory | Purpose |
|------------------|---------|
| `app.py` | FastAPI server that serves static files and manages WebSocket connections. |
| `static/index.html` | Main UI page (chat, logs, download button). |
| `static/style.css` | Modern dark‑theme styling with gradients, animations and responsive layout. |
| `search_agent.py` | Core `SearchAgent` class orchestrating the cognitive loop. |
| `perception.py` | Extracts intent, entities and tool hints from raw user input using Gemini. |
| `memory.py` | FAISS‑based vector store (`MemoryManager`) for storing and retrieving `MemoryItem`s. |
| `decision.py` | Generates a plan (tool call or final answer) based on perception, memory and conversation history. |
| `action.py` | Parses `FUNCTION_CALL` strings and executes the corresponding MCP tool. |
| `agent.py` | Helper utilities (logging, constants). |
| `faiss_index/` | Serialized FAISS index and metadata for the vector store. |
| `documents/` | Folder where downloaded resources are saved. |
| `README.md` | This documentation. |

## Cognitive Layers (4‑step Process)
1. **Perception** – `extract_perception` turns the raw user text into a `PerceptionResult` (intent, entities, optional tool hint). 
2. **Memory** – `MemoryManager` stores each interaction as a `MemoryItem` and retrieves the most relevant items using vector similarity. 
3. **Decision** – `generate_plan` builds a prompt that includes perception data, retrieved memories and recent chat history, then asks Gemini to either:
   - return a `FUNCTION_CALL` (e.g., `search_documents|query=...`) or
   - return a `FINAL_ANSWER`. 
4. **Action** – `parse_function_call` extracts the tool name and arguments, `execute_tool` calls the MCP tool, and the result is fed back into memory for the next loop.

## How It Works (Simplified Flow)
```
User → WebSocket → SearchAgent.run()
    ├─ Perception → intent, entities, tool_hint
    ├─ Memory.retrieve(query) → relevant past items
    ├─ Decision (LLM) → FUNCTION_CALL or FINAL_ANSWER
    └─ Action (if FUNCTION_CALL) → tool execution → result → Memory.add()
```
The loop repeats until the LLM emits `FINAL_ANSWER`, which is sent back to the UI.

## Setup & Running
1. **Install dependencies**
   ```bash
   pip install -r requirements.txt   # or use uv if preferred
   ```
2. **Configure environment** – create a `.env` file with:
   ```
   GEMINI_API_KEY=your-gemini-key
   LOCAL_HOST=http://127.0.0.1:8000/
   LOCAL_OLLAMA_API_KEY=your-ollama-key   # if using Ollama embeddings
   ```
3. **Start the server**
   ```bash
   uv run app.py
   ```
4. Open a browser at `http://127.0.0.1:8000` – the chat UI will appear.

## Using the UI
- Type a question or topic in the input box and press **Send**.
- The chat area shows the conversation; the **Download Report** button saves a zip with the session’s resources.
- Live logs (bottom) display internal events such as tool calls and status changes.

## Extending the Agent
- **Add a new tool**: implement the tool in the MCP server, then reference it in `tool_descriptions` (passed to `generate_plan`).
- **Change the LLM**: modify the Gemini model name in `perception.py` and `decision.py`.
- **Swap the vector store**: replace `MemoryManager` with another embedding backend; keep the same `add`/`retrieve` interface.

## Important Notes
- The UI is cached aggressively; clear your browser cache (Ctrl + F5) after code changes.
- All logs are printed to the terminal and also streamed to the web UI via WebSocket.
- The FAISS index is stored under `faiss_index/`; delete it to force a full re‑index.

---
Happy hacking! 🚀
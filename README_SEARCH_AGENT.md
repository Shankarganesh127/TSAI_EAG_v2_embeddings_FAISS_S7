# Search Agent V2 - Setup & Run Instructions

The Search Agent has been set up with a FastAPI backend, a WebSocket-based agent loop, and a premium Web UI.

## 1. Install Dependencies
Since you are using `uv`, run the following command in your terminal:

```powershell
uv pip install -r pyproject.toml
```
*Note: If `uv` doesn't support installing directly from `pyproject.toml` in your version, use:*
```powershell
uv pip install mcp fastapi uvicorn websockets duckduckgo-search beautifulsoup4 faiss-cpu numpy openai python-dotenv pillow markitdown google-genai requests pydantic
```

## 2. Run the Application
Start the FastAPI server which hosts both the UI and the Agent:

```powershell
python app.py
```

## 3. Use the Agent
1. Open your browser and navigate to: `http://localhost:8000`
2. You will see the **Search Agent Dashboard**.
3. Enter a topic (e.g., "Generative AI") in the chat on the left.
4. The agent will:
   - **Perceive** your intent.
   - **Check Memory** (FAISS) for existing info.
   - **Decide** to search the web if needed.
   - **Act** (Search, Fetch, Embed).
   - **Respond** in the chat.
5. You can see the internal state in the "Agent Layers" section and logs in the "Live Logs" terminal.
6. Click **Download Report** to get a zip of all collected resources and history.

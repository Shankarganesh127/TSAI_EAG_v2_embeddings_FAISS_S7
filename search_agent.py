import asyncio
import time
import os
import datetime
import sys
import json
from typing import Callable, Optional, List, Dict, Any
from perception import extract_perception
from memory import MemoryManager, MemoryItem
from decision import generate_plan
from action import execute_tool
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from contextlib import AsyncExitStack

class SearchAgent:
    def __init__(self, callback: Callable[[str, Any], None]):
        self.callback = callback
        self.memory = MemoryManager()
        self.session_id = f"session-{int(time.time())}"
        self.history: List[Dict[str, Any]] = []
        self.input_queue = asyncio.Queue()
        self.running = False
        self.tools_list = []
        self.tool_descriptions = ""
        self.current_topic = None

    def log(self, stage: str, msg: str):
        now = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"[{now}] [{stage}] {msg}")
        self.callback("log", {"stage": stage, "message": msg, "timestamp": now})

    async def run(self):
        self.running = True
        self.log("agent", "Starting Search Agent...")
        
        server_params = StdioServerParameters(
            command=sys.executable,
            args=["server_v3.py"],
            cwd=os.getcwd()
        )

        async with AsyncExitStack() as stack:
            try:
                read, write = await stack.enter_async_context(stdio_client(server_params))
                session = await stack.enter_async_context(ClientSession(read, write))
                await session.initialize()
                
                self.log("agent", "Connected to MCP Server")
                
                # List tools
                tools_result = await session.list_tools()
                self.tools_list = tools_result.tools
                self.tool_descriptions = "\n".join(
                    f"- {tool.name}: {getattr(tool, 'description', 'No description')}" 
                    for tool in self.tools_list
                )
                self.log("agent", f"Loaded {len(self.tools_list)} tools")
                self.callback("tools", [t.name for t in self.tools_list])

                while self.running:
                    user_input = await self.input_queue.get()
                    if user_input == "EXIT":
                        break
                    
                    await self.process_request(session, user_input)
                    
            except Exception as e:
                self.log("error", f"Agent crashed: {e}")
                import traceback
                traceback.print_exc()
            finally:
                self.log("agent", "Agent stopped")

    async def process_request(self, session, user_input: str):
        self.log("user", f"Input: {user_input}")
        self.history.append({"role": "user", "content": user_input, "timestamp": datetime.datetime.now().isoformat()})
        self.callback("chat", {"role": "user", "content": user_input})

        if self.current_topic is None:
            self.current_topic = user_input

        step = 0
        max_steps = 50 # Increased limit
        
        # Determine query for retrieval
        if len(user_input.split()) < 5 or "summarize" in user_input.lower() or "continue" in user_input.lower():
            query = f"{user_input} related to {self.current_topic}"
        else:
            query = user_input
            self.current_topic = user_input
        
        # 1. Perception
        self.callback("layer", {"name": "Perception", "status": "active"})
        perception = extract_perception(user_input)
        self.log("perception", f"Intent: {perception.intent}, Tool hint: {perception.tool_hint}")
        self.callback("layer", {"name": "Perception", "status": "done", "data": perception.dict()})

        # Check if user wants to stop or finish based on previous interaction
        if perception.intent and ("stop" in perception.intent.lower() or "finish" in perception.intent.lower()):
             # Force a final answer generation based on memory
             query = f"Summarize everything found about {self.current_topic} and provide the final answer."

        search_count = 0

        while step < max_steps:
            # 2. Memory
            self.callback("layer", {"name": "Memory", "status": "active"})
            retrieved = self.memory.retrieve(query=query, top_k=5, session_filter=self.session_id)
            self.log("memory", f"Retrieved {len(retrieved)} relevant memories")
            self.callback("layer", {"name": "Memory", "status": "done", "data": [m.dict() for m in retrieved]})

            # 3. Decision
            self.callback("layer", {"name": "Decision", "status": "active"})
            plan = generate_plan(perception, retrieved, tool_descriptions=self.tool_descriptions, history=self.history)
            self.log("plan", f"Plan: {plan}")
            self.callback("layer", {"name": "Decision", "status": "done", "data": {"plan": plan}})

            if plan.startswith("FINAL_ANSWER:"):
                answer = plan.replace("FINAL_ANSWER:", "").strip()
                self.log("agent", f"Answer: {answer}")
                self.history.append({"role": "assistant", "content": answer, "timestamp": datetime.datetime.now().isoformat()})
                self.callback("chat", {"role": "assistant", "content": answer})
                break

            # 4. Action
            self.callback("layer", {"name": "Action", "status": "active"})
            try:
                result = await execute_tool(session, self.tools_list, plan)
                self.log("tool", f"{result.tool_name} -> {str(result.result)[:100]}...")
                
                # Store result in memory
                memory_item = MemoryItem(
                    text=f"Tool {result.tool_name} output: {result.result}",
                    type="tool_output",
                    tool_name=result.tool_name,
                    user_query=query,
                    tags=[result.tool_name],
                    session_id=self.session_id
                )
                self.memory.add(memory_item)
                
                # Add to history
                self.history.append({
                    "role": "tool", 
                    "name": result.tool_name, 
                    "content": str(result.result), 
                    "timestamp": datetime.datetime.now().isoformat()
                })
                
                # If we found resources, notify UI
                if result.tool_name in ["web_search", "search_documents"]:
                     self.callback("resources", {"type": "search", "data": str(result.result)})
                     search_count += 1
                
                # If open_url was called, extract URL and notify frontend
                if result.tool_name == "open_url" and isinstance(result.result, str) and result.result.startswith("OPEN_URL:"):
                    url = result.result.replace("OPEN_URL:", "").strip()
                    self.callback("open_url", {"url": url})

                self.callback("layer", {"name": "Action", "status": "done", "data": {"tool": result.tool_name, "result": str(result.result)[:200]}})
                
                # Checkpoint every 5 searches
                if search_count > 0 and search_count % 5 == 0:
                    msg = "I have performed 5 searches. Do you want me to continue searching for more information, or should I summarize what I have found so far?"
                    self.log("agent", "Checkpoint reached.")
                    self.history.append({"role": "assistant", "content": msg, "timestamp": datetime.datetime.now().isoformat()})
                    self.callback("chat", {"role": "assistant", "content": msg})
                    return # Exit loop and wait for user input

                # Update query for next iteration
                query = f"Original: {user_input}\nPrevious Tool Output: {result.result}\nWhat next?"

            except Exception as e:
                self.log("error", f"Tool execution failed: {e}")
                self.callback("chat", {"role": "assistant", "content": f"I encountered an error: {e}"})
                break
            
            step += 1
        
        if step >= max_steps:
             self.callback("chat", {"role": "assistant", "content": "I reached the step limit. Shall I summarize what I found?"})

    def get_history(self):
        return self.history

if __name__ == "__main__":
    # Simple test
    async def test():
        agent = SearchAgent(lambda t, d: print(f"EVENT {t}: {d}"))
        asyncio.create_task(agent.run())
        await asyncio.sleep(2)
        await agent.input_queue.put("What is the capital of France?")
        await asyncio.sleep(10)
        await agent.input_queue.put("EXIT")
    
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(test())

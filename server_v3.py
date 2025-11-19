from mcp.server.fastmcp import FastMCP, Image
from dotenv import load_dotenv
from mcp.server.fastmcp.prompts import base
from mcp.types import TextContent
from mcp import types
from PIL import Image as PILImage
import math
import sys
import os
import json
import faiss
import numpy as np
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from ddgs import DDGS
from markitdown import MarkItDown
import time
from tqdm import tqdm
import hashlib
from openai import OpenAI
from pydantic import BaseModel

class AddInput(BaseModel):
    a: int
    b: int

class AddOutput(BaseModel):
    result: int

class SqrtInput(BaseModel):
    a: float

class SqrtOutput(BaseModel):
    result: float

class StringsToIntsInput(BaseModel):
    string: str

class StringsToIntsOutput(BaseModel):
    ascii_values: list[int]

class ExpSumInput(BaseModel):
    int_list: list[int]

class ExpSumOutput(BaseModel):
    result: float

load_dotenv()
mcp = FastMCP("SearchAgentServer")

SERVER_URL = os.getenv("LOCAL_HOST")
API_KEY = os.getenv("LOCAL_OLLAMA_API_KEY")
EMBED_MODEL = "nomic-embed-text:latest"

client = OpenAI(
    base_url=f"{SERVER_URL}api",
    api_key=API_KEY,
)

CHUNK_SIZE = 256
CHUNK_OVERLAP = 40
ROOT = Path(__file__).parent.resolve()

def get_embedding(text: str) -> np.ndarray:
    try:
        response = client.embeddings.create(
            model=EMBED_MODEL,
            input=text
        )
        return np.array(response.data[0].embedding, dtype=np.float32)
    except Exception as e:
        sys.stderr.write(f"Error generating embedding: {e}\n")
        raise

def chunk_text(text, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    words = text.split()
    for i in range(0, len(words), size - overlap):
        yield " ".join(words[i:i+size])

def mcp_log(level: str, message: str) -> None:
    """Log a message to stderr to avoid interfering with JSON communication"""
    sys.stderr.write(f"{level}: {message}\n")
    sys.stderr.flush()

@mcp.tool()
def web_search(query: str, max_results: int = 5) -> str:
    """Search the internet for a given query using DuckDuckGo."""
    mcp_log("SEARCH", f"Searching for: {query}")
    try:
        results = DDGS().text(query, max_results=max_results)
        formatted_results = []
        for r in results:
            formatted_results.append(f"Title: {r['title']}\nURL: {r['href']}\nSnippet: {r['body']}\n")
        return "\n".join(formatted_results)
    except Exception as e:
        return f"ERROR: Search failed: {str(e)}"

@mcp.tool()
def open_url(url: str) -> str:
    """Open a URL in the user's browser to show proof or evidence."""
    mcp_log("OPEN_URL", f"Opening: {url}")
    return f"OPEN_URL:{url}"

@mcp.tool()
def fetch_url(url: str) -> str:
    """Fetch and extract text content from a URL."""
    mcp_log("FETCH", f"Fetching URL: {url}")
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
            
        text = soup.get_text()
        # Break into lines and remove leading/trailing space on each
        lines = (line.strip() for line in text.splitlines())
        # Break multi-headlines into a line each
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        # Drop blank lines
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        # Save to a file for processing
        filename = f"downloaded_{int(time.time())}.txt"
        filepath = ROOT / "documents" / filename
        filepath.parent.mkdir(exist_ok=True)
        filepath.write_text(f"Source: {url}\n\n{text}", encoding='utf-8')
        
        return f"Successfully fetched content from {url}. Saved to {filename}. Content preview:\n{text[:500]}..."
    except Exception as e:
        return f"ERROR: Failed to fetch URL: {str(e)}"

@mcp.tool()
def search_documents(query: str) -> list[str]:
    """Search for relevant content from uploaded documents."""
    ensure_faiss_ready()
    mcp_log("SEARCH", f"Query: {query}")
    try:
        index = faiss.read_index(str(ROOT / "faiss_index" / "index.bin"))
        metadata = json.loads((ROOT / "faiss_index" / "metadata.json").read_text())
        query_vec = get_embedding(query).reshape(1, -1)
        D, I = index.search(query_vec, k=5)
        results = []
        for idx in I[0]:
            if idx < len(metadata):
                data = metadata[idx]
                results.append(f"{data['chunk']}\n[Source: {data['doc']}, ID: {data['chunk_id']}]")
        return results
    except Exception as e:
        return [f"ERROR: Failed to search: {str(e)}"]

@mcp.tool()
def trigger_process_documents() -> str:
    """Manually trigger document processing and indexing."""
    mcp_log("INFO", "Triggering document processing...")
    process_documents()
    return "Document processing completed."

# --- Existing Math Tools ---
@mcp.tool()
def add(input: AddInput) -> AddOutput:
    return AddOutput(result=input.a + input.b)

@mcp.tool()
def sqrt(input: SqrtInput) -> SqrtOutput:
    return SqrtOutput(result=input.a ** 0.5)

@mcp.tool()
def subtract(a: int, b: int) -> int:
    return int(a - b)

@mcp.tool()
def multiply(a: int, b: int) -> int:
    return int(a * b)

@mcp.tool()
def divide(a: int, b: int) -> float:
    return float(a / b)

@mcp.tool()
def power(a: int, b: int) -> int:
    return int(a ** b)

@mcp.tool()
def cbrt(a: int) -> float:
    return float(a ** (1/3))

@mcp.tool()
def factorial(a: int) -> int:
    return int(math.factorial(a))

@mcp.tool()
def log_tool(a: int) -> float: # Renamed to avoid conflict with log function
    return float(math.log(a))

@mcp.tool()
def remainder(a: int, b: int) -> int:
    return int(a % b)

@mcp.tool()
def sin(a: int) -> float:
    return float(math.sin(a))

@mcp.tool()
def cos(a: int) -> float:
    return float(math.cos(a))

@mcp.tool()
def tan(a: int) -> float:
    return float(math.tan(a))

@mcp.tool()
def mine(a: int, b: int) -> int:
    return int(a - b - b)

@mcp.tool()
def create_thumbnail(image_path: str) -> Image:
    img = PILImage.open(image_path)
    img.thumbnail((100, 100))
    return Image(data=img.tobytes(), format="png")

@mcp.tool()
def strings_to_chars_to_int(input: StringsToIntsInput) -> StringsToIntsOutput:
    ascii_values = [ord(char) for char in input.string]
    return StringsToIntsOutput(ascii_values=ascii_values)

@mcp.tool()
def int_list_to_exponential_sum(input: ExpSumInput) -> ExpSumOutput:
    result = sum(math.exp(i) for i in input.int_list)
    return ExpSumOutput(result=result)

@mcp.tool()
def fibonacci_numbers(n: int) -> list:
    if n <= 0:
        return []
    fib_sequence = [0, 1]
    for _ in range(2, n):
        fib_sequence.append(fib_sequence[-1] + fib_sequence[-2])
    return fib_sequence[:n]

# --- Resources & Prompts ---
@mcp.resource("greeting://{name}")
def get_greeting(name: str) -> str:
    return f"Hello, {name}!"

@mcp.prompt()
def review_code(code: str) -> str:
    return f"Please review this code:\n\n{code}"

@mcp.prompt()
def debug_error(error: str) -> list[base.Message]:
    return [
        base.UserMessage("I'm seeing this error:"),
        base.UserMessage(error),
        base.AssistantMessage("I'll help debug that. What have you tried so far?"),
    ]

def process_documents():
    """Process documents and create FAISS index"""
    mcp_log("INFO", "Indexing documents with MarkItDown...")
    ROOT = Path(__file__).parent.resolve()
    DOC_PATH = ROOT / "documents"
    DOC_PATH.mkdir(exist_ok=True) # Ensure directory exists
    INDEX_CACHE = ROOT / "faiss_index"
    INDEX_CACHE.mkdir(exist_ok=True)
    INDEX_FILE = INDEX_CACHE / "index.bin"
    METADATA_FILE = INDEX_CACHE / "metadata.json"
    CACHE_FILE = INDEX_CACHE / "doc_index_cache.json"

    def file_hash(path):
        return hashlib.md5(Path(path).read_bytes()).hexdigest()

    CACHE_META = json.loads(CACHE_FILE.read_text()) if CACHE_FILE.exists() else {}
    metadata = json.loads(METADATA_FILE.read_text()) if METADATA_FILE.exists() else []
    index = faiss.read_index(str(INDEX_FILE)) if INDEX_FILE.exists() else None
    all_embeddings = []
    converter = MarkItDown()

    files_processed = 0
    for file in DOC_PATH.glob("*.*"):
        fhash = file_hash(file)
        if file.name in CACHE_META and CACHE_META[file.name] == fhash:
            continue

        mcp_log("PROC", f"Processing: {file.name}")
        try:
            result = converter.convert(str(file))
            markdown = result.text_content
            chunks = list(chunk_text(markdown))
            embeddings_for_file = []
            new_metadata = []
            for i, chunk in enumerate(chunks):
                embedding = get_embedding(chunk)
                embeddings_for_file.append(embedding)
                new_metadata.append({"doc": file.name, "chunk": chunk, "chunk_id": f"{file.stem}_{i}"})
            if embeddings_for_file:
                if index is None:
                    dim = len(embeddings_for_file[0])
                    index = faiss.IndexFlatL2(dim)
                index.add(np.stack(embeddings_for_file))
                metadata.extend(new_metadata)
            CACHE_META[file.name] = fhash
            files_processed += 1
        except Exception as e:
            mcp_log("ERROR", f"Failed to process {file.name}: {e}")

    CACHE_FILE.write_text(json.dumps(CACHE_META, indent=2))
    METADATA_FILE.write_text(json.dumps(metadata, indent=2))
    if index and index.ntotal > 0:
        faiss.write_index(index, str(INDEX_FILE))
        mcp_log("SUCCESS", f"Saved FAISS index and metadata. Processed {files_processed} new files.")
    else:
        mcp_log("WARN", "No new documents or updates to process.")

def ensure_faiss_ready():
    index_path = ROOT / "faiss_index" / "index.bin"
    meta_path = ROOT / "faiss_index" / "metadata.json"
    if not (index_path.exists() and meta_path.exists()):
        mcp_log("INFO", "Index not found — running process_documents()...")
        process_documents()

if __name__ == "__main__":
    sys.stderr.write("STARTING SERVER V3\n")
    if len(sys.argv) > 1 and sys.argv[1] == "dev":
        mcp.run()
    else:
        import threading
        server_thread = threading.Thread(target=lambda: mcp.run(transport="stdio"))
        server_thread.daemon = True
        server_thread.start()
        time.sleep(2)
        process_documents()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            sys.stderr.write("\nShutting down...\n")

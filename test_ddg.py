from duckduckgo_search import DDGS
import sys

try:
    print("Testing DDGS...")
    results = DDGS().text("future of AI impact on world economy", max_results=5)
    print(f"Results found: {len(results)}")
    for r in results:
        print(f"- {r['title']}")
except Exception as e:
    print(f"DDGS Failed: {e}")
    import traceback
    traceback.print_exc()

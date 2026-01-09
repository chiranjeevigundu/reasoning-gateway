import httpx
import json
import sys

GATEWAY_URL = "http://localhost:8000/chat/completions"

def run_test():
    print(f"--- Connecting to Gateway {GATEWAY_URL} ---")
    
    # Define the test payload with a query that requires reasoning
    payload = {
        "messages": [{"role": "user", "content": "why is the sky blue?"}],
        "stream": True
    }

    try:
        # Initiate the streaming request to the Gateway
        with httpx.stream("POST", GATEWAY_URL, json=payload, timeout=60) as response:
            print("\n[INCOMING STREAM]\n")
            
            for line in response.iter_lines():
                if not line.startswith("data: "): continue
                data = line[6:].strip()
                if data == "[DONE]": break
                
                try:
                    event = json.loads(data)
                    etype = event.get("type")
                    content = event.get("content", "")

                    # Process incoming Server-Sent Events (SSE)
                    if etype == "prompt_summary":
                        print(f"[PROMPT]: {content}")
                        print(f"\n[REASONING]: ", end="", flush=True)
                    
                    elif etype == "reasoning_content":
                        # Calculated reasoning content streaming in real-time
                        sys.stdout.write(content)
                        sys.stdout.flush()

                    elif etype == "reasoning_summary":
                        # Reasoning complete. Display the summary and prepare for the final answer.
                        print(f"\n\n[REASONING SUMMARY]: {content}")
                        print(f"\n[FINAL RESPONSE]: ", end="", flush=True)
                    
                    elif etype == "content":
                        # Standard content (final answer) streaming
                        sys.stdout.write(content)
                        sys.stdout.flush()
                except: pass
            print("\n\n[DONE]")
            
    except Exception as e:
        print(f"Connection Error: {e}")

if __name__ == "__main__":
    run_test()
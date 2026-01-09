import os
import json
import re
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from typing import Dict, Any, AsyncGenerator

UPSTREAM_URL = os.getenv("UPSTREAM_URL", "http://127.0.0.1:8001/chat/completions")

app = FastAPI()

def smart_summarizer(text: str) -> str:
    """Creates a clean summary of the reasoning steps."""
    clean_text = text.replace('\n', ' ').strip()
    if not clean_text: return "Analysis performed."

    # Strategy 1: Look for "First", "Then", "Finally" keywords or numbers
    # This helps extract logic even if numbering is messy
    steps = re.findall(r'(?:First|Then|Next|Finally|\d+\.)\s+([^.,]+)', clean_text, re.IGNORECASE)
    
    if len(steps) >= 2:
        # Join top 3 steps
        summary = "; ".join(steps[:3])
        return f"Logic trace: {summary}..."
    
    # Strategy 2: First and Last Sentence (Robust Fallback)
    # Split by periods, but allow for some messiness
    sentences = [s.strip() for s in clean_text.split('.') if len(s.strip()) > 10]
    if len(sentences) >= 2:
        return f"The model started with '{sentences[0][:40]}...' and concluded that '{sentences[-1][:40]}...'"

    # Fallback: Just take the first 15 words
    words = clean_text.split(' ')
    preview = " ".join(words[:15])
    return f"Quick thought: {preview}..."

async def stream_processor(request_body: Dict[str, Any], upstream_url: str) -> AsyncGenerator[str, None]:
    client = httpx.AsyncClient(timeout=60.0)
    
    # 1. Prompt Summary
    # Extract the latest user message to provide an immediate acknowledgment event.
    messages = request_body.get("messages", [])
    user_prompt = messages[-1]["content"] if messages else "Unknown"
    yield f"data: {json.dumps({'type': 'prompt_summary', 'content': user_prompt[:100]})}\n\n"

    try:
        async with client.stream("POST", upstream_url, json=request_body) as response:
            buffer = ""
            in_thinking_block = False

            async for line in response.aiter_lines():
                if not line.startswith("data: "): continue
                raw = line[6:].strip()
                if raw == "[DONE]": break

                try:
                    chunk = json.loads(raw)
                    delta = chunk["choices"][0]["delta"].get("content", "")
                    if not delta: continue

                    # --- PROCESSING PIPELINE ---
                    # The stream is separated into two channels: "Reasoning" and "Final Content".
                    
                    if "<think>" in delta:
                        in_thinking_block = True
                        parts = delta.split("<think>")
                        # If content exists before the thinking block, emit it first.
                        if parts[0]: 
                            yield f"data: {json.dumps({'type': 'content', 'content': parts[0]})}\n\n"
                        
                        buffer += parts[1]
                        # Stream the ongoing reasoning tokens to the client.
                        if parts[1]:
                            yield f"data: {json.dumps({'type': 'reasoning_content', 'content': parts[1]})}\n\n"
                        continue

                    if "</think>" in delta:
                        in_thinking_block = False
                        parts = delta.split("</think>")
                        buffer += parts[0]
                        if parts[0]:
                            yield f"data: {json.dumps({'type': 'reasoning_content', 'content': parts[0]})}\n\n"
                        
                        # Reasoning is complete. Generate and emit the summary.
                        summary = smart_summarizer(buffer)
                        yield f"data: {json.dumps({'type': 'reasoning_summary', 'content': summary})}\n\n"
                        
                        buffer = ""
                        if len(parts) > 1 and parts[1]:
                            # Filter out any hallucinated closing tags from the beginning of the answer.
                            clean_part1 = re.sub(r'</?[\w]+>', '', parts[1])
                            if clean_part1:
                                yield f"data: {json.dumps({'type': 'content', 'content': clean_part1})}\n\n"
                        continue

                    if in_thinking_block:
                        buffer += delta
                        yield f"data: {json.dumps({'type': 'reasoning_content', 'content': delta})}\n\n"
                    else:
                        # Ensure the final answer is clean by removing XML-like artifacts.
                        clean_delta = re.sub(r'</?[\w]+>', '', delta)
                        if clean_delta:
                            yield f"data: {json.dumps({'type': 'content', 'content': clean_delta})}\n\n"

                except Exception: pass
            
            yield "data: [DONE]\n\n"

    except Exception as e:
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
    finally:
        await client.aclose()

@app.post("/chat/completions")
async def gateway(request: Request):
    try: body = await request.json()
    except: return {"error": "Invalid JSON"}
    return StreamingResponse(stream_processor(body, UPSTREAM_URL), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
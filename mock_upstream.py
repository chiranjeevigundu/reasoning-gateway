import uvicorn
import json
import time
import torch
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from transformers import AutoModelForCausalLM, AutoTokenizer, TextIteratorStreamer
from threading import Thread

app = FastAPI()

# Using Qwen2.5-0.5B-Instruct
MODEL_ID = "Qwen/Qwen2.5-0.5B-Instruct"

print(f"Loading {MODEL_ID}...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
model = AutoModelForCausalLM.from_pretrained(MODEL_ID, torch_dtype="auto", device_map="auto")
print("Model loaded successfully!")

def generate_stream(messages):
    # 1. System Prompt Configuration
    # We define a strict system prompt to enforce the reasoning structure.
    # We require the model to output a <think> block before the final answer.
    system_prompt = (
        "You are a rigorous reasoning engine. "
        "Before answering, you must output a <think> block.\n"
        "Inside <think>, you must:\n"
        "1. Deconstruct the user's query.\n"
        "2. List known facts related to the query.\n"
        "3. Verify your logic step-by-step.\n"
        "4. Formulate the final answer.\n"
        "Close with </think> and then output the final answer."
    )
    
    user_content = messages[-1]["content"]
    
    # 2. Prompt Engineering
    # We use one-shot examples to demonstrate the expected format (Thinking vs Answer).
    refined_messages = [
        {"role": "system", "content": system_prompt},
        # One-shot: Simple math
        {"role": "user", "content": "What is 2+2?"},
        {"role": "assistant", "content": "<think>1. Analyze input: The user asks for the sum of 2 and 2.\n2. Recall arithmetic rules: The operation is addition.\n3. Calculation: 2 + 2 = 4.\n4. Verification: The result is consistent with standard math.</think>The answer is 4."},
        # One-shot: Fact
        {"role": "user", "content": "Capital of France?"},
        {"role": "assistant", "content": "<think>1. Identify entity: France.\n2. Retrieve knowledge: The capital is typically Paris.\n3. Verify: Paris is the political and cultural center.\n4. Conclusion: Paris is the correct answer.</think>Paris."},
        # Actual request
        {"role": "user", "content": user_content}
    ]

    # 3. Forced Prefix Injection
    # We append <think> to the prompt to force the model to begin reasoning immediately.
    input_text = tokenizer.apply_chat_template(refined_messages, tokenize=False, add_generation_prompt=True)
    forced_prompt = input_text + "<think>"
    
    inputs = tokenizer(forced_prompt, return_tensors="pt").to(model.device)
    streamer = TextIteratorStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)
    
    # 4. Generation
    # We use a slightly higher temperature to encourage detailed reasoning.
    generation_kwargs = dict(
        inputs, 
        streamer=streamer, 
        max_new_tokens=512, 
        temperature=0.6, 
        do_sample=True
    )
    
    thread = Thread(target=model.generate, kwargs=generation_kwargs)
    thread.start()
    
    chunk_id = f"chatcmpl-{int(time.time())}"
    
    # 5. Inject Start Token
    # Manually yield the <think> tag since it was part of the prompt, not the generation.
    start_chunk = {
        "id": chunk_id, "object": "chat.completion.chunk", "created": int(time.time()), "model": MODEL_ID,
        "choices": [{"index": 0, "delta": {"content": "<think>"}, "finish_reason": None}]
    }
    yield f"data: {json.dumps(start_chunk)}\n\n"
    
    # 6. Stream Response
    # Yield the remaining tokens as they are generated.
    print("Generating: <think>", end="", flush=True)
    for new_text in streamer:
        print(new_text, end="", flush=True)
        chunk = {
            "id": chunk_id, "object": "chat.completion.chunk", "created": int(time.time()), "model": MODEL_ID,
            "choices": [{"index": 0, "delta": {"content": new_text}, "finish_reason": None}]
        }
        yield f"data: {json.dumps(chunk)}\n\n"
        
    print("\n[Done]")
    yield "data: [DONE]\n\n"

@app.post("/chat/completions")
async def chat_endpoint(request: Request):
    data = await request.json()
    return StreamingResponse(generate_stream(data.get("messages", [])), media_type="text/event-stream")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
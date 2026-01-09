# Inference API Gateway

## Overview
This repository contains the solution for the "Inference API" problem. It implements a Python-based Gateway Server that sits in front of an existing `/chat/completions` API (simulated by `mock_upstream.py` using Qwen2.5-0.5B) and provides an enhanced streaming experience.

## The Problem
Reasoning-capable LLMs produce verbose thinking traces. To improve usability, this gateway:
1.  Connects to an upstream provider.
2.  Parses the streaming response.
3.  Returns structured content in a specific order:
    -   Prompt Summary
    -   Reasoning Summary (plus real-time reasoning traces)
    -   Final Response

## Project Structure
`gateway.py` - The Gateway Implementation. Uses FastAPI to proxy requests, maintain state, and stream specialized instruction-aware SSE events.

`mock_upstream.py` - Simulated Upstream API. Runs a local LLM (`Qwen2.5-0.5B-Instruct`), enforces a `<think>` block via system prompts, and streams strict JSON chunks.

`client.py` - Client Script. Demonstrates how to connect to the Gateway, parse the custom SSE format, and display the ordered output.

`Dockerfile` - Container definition for the Gateway server. 

`docker-compose.yml` - Simple orchestration to run the Gateway alongside the local Upstream service. 

## How to Run & Test
### Prerequisites
  Python 3.11+
  Docker (Optional, but recommended for the Gateway)

### Step 1: Start the Mock Upstream (Local)
We run the upstream model on the host to utilize hardware acceleration without complex Docker GPU pass-through.
```bash
python mock_upstream.py
```
Listening on: `http://localhost:8001`

### Step 2: Start the Gateway
You can run the gateway locally or via Docker.

**Option A: Docker (Recommended)**
```bash
docker-compose up --build
```

**Option B: Local Python**
```bash
pip install -r requirements.gateway.txt
python gateway.py
```
Listening on: `http://localhost:8000`

### Step 3: Run the Test Client
```bash
python client.py
```

## Expected Output
The client will output the stream in the following order:
1.  [PROMPT]: a summary of what you asked.
2.  [REASONING]: The real-time thinking process (optional visibility).
3.  [REASONING SUMMARY]: A concise extraction of the logic path.
4.  [FINAL RESPONSE]: The clean model output.
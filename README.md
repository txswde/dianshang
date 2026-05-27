# dianshang

dianshang is an AI Agent based e-commerce customer service system built with FastAPI, Vue 3, LangGraph, Neo4j, Redis, MySQL, and large language models.

## Features

- Multi-agent workflow orchestration with LangGraph
- Intent routing for general chat, clarification, knowledge graph query, image understanding, and file processing
- Guardrails for privacy, out-of-scope questions, over-promising, and unsafe business responses
- Tool calling for Neo4j/Cypher query, GraphRAG query, web search, image analysis, and file parsing
- Streaming responses with Server-Sent Events
- Conversation persistence with MySQL
- Semantic cache for repeated or similar questions with Redis
- Vue 3 chat UI with conversation history, file upload, image upload, search panel, and e-commerce customer service page

## Tech Stack

- Backend: Python, FastAPI, SQLAlchemy, MySQL, Redis, LangGraph, LangChain
- LLM: DeepSeek API, Ollama
- Knowledge and tools: Neo4j, Cypher, GraphRAG, SerpAPI
- Frontend: Vue 3, TypeScript, Pinia, Vite

## Project Structure

```text
01_AssistGen_houduan/              Backend service
02_AssistGen_qianduan/             Frontend service
run_test.py                        Offline evaluation script
```

## Backend Setup

```bash
cd 01_AssistGen_houduan
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Create `llm_backend/.env` and configure the required services:

```env
CHAT_SERVICE=DEEPSEEK
REASON_SERVICE=DEEPSEEK
AGENT_SERVICE=DEEPSEEK

DEEPSEEK_API_KEY=your-api-key
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat

DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your-password
DB_NAME=assistgen

REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-password
NEO4J_DATABASE=neo4j

SERPAPI_KEY=your-serpapi-key
SECRET_KEY=replace-with-a-secure-secret
```

Start the backend:

```bash
cd llm_backend
python run.py
```

## Frontend Setup

```bash
cd 02_AssistGen_qianduan/DsAgentChat_web
npm install
npm run dev
```

## Evaluation

`run_test.py` contains an offline evaluation set for e-commerce customer service scenarios, covering product query, recommendation, inventory, pricing, and guardrail cases.

```bash
python run_test.py
```

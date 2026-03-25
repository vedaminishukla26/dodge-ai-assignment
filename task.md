# Dodge AI — Graph-Based O2C Query System

## Phase 1: Project Scaffolding & Docker Setup
- [x] Create backend (FastAPI) with Dockerfile
- [x] Create frontend (Vite + React + TypeScript) with Dockerfile
- [x] Create [docker-compose.yml](file:///Users/parjanya-heaven/Desktop/dodge-ai/docker-compose.yml) with Neo4j, Postgres, API, Web services
- [x] Create [.env.example](file:///Users/parjanya-heaven/Desktop/dodge-ai/.env.example) and environment config
- [x] Pushed to GitHub

## Phase 2: Data Modeling & Ingestion
- [x] Define Neo4j graph schema (nodes, relationships)
- [x] Write data ingestion script to load JSONL → Neo4j
- [x] Set up Postgres models for chat history
- [ ] Verify graph is populated, queryable in Neo4j browser

## Phase 3: GenAI Query Engine
- [ ] Implement Text-to-Cypher with LangChain + Gemini
- [ ] Add guardrail middleware for off-topic queries
- [ ] Create FastAPI endpoints for chat queries
- [ ] Test query → Cypher → result pipeline

## Phase 4: Frontend UI
- [ ] Build dashboard layout (sidebar chat + graph canvas)
- [ ] Integrate graph visualization library
- [ ] Build chat interface with streaming responses
- [ ] Add sample query cards

## Phase 5: Integration & Polish
- [ ] Node highlighting from query results
- [ ] Trace-flow visualization
- [ ] Expand/collapse node interactions
- [ ] Final UI polish and responsiveness

## Phase 6: Packaging
- [ ] Docker health checks, one-command startup
- [ ] Final README with instructions

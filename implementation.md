# Dodge AI — Graph-Based O2C Query System

Build a full-stack application that ingests SAP Order-to-Cash data into Neo4j, visualizes it as an interactive graph, and lets users query it via natural language (Text-to-Cypher powered by Gemini).

## User Review Required

> [!IMPORTANT]
> **Architecture Decision — Docker-Based Multi-Service Stack**: Per your `plan.txt`, we'll use:
> - **Neo4j** for graph storage and Cypher queries
> - **PostgreSQL** for chat history
> - **FastAPI** (Python) for backend API + LLM orchestration
> - **React + Vite + TypeScript** for frontend
> - **Docker Compose** to orchestrate everything
>
> **LLM**: Google Gemini 1.5 Flash (free tier). You'll need a `GOOGLE_API_KEY`.
>
> **Graph Visualization**: `react-force-graph-2d` library.

> [!WARNING]
> You need a **Google Gemini API key** (free tier from [aistudio.google.com](https://aistudio.google.com)). This must be set as `GOOGLE_API_KEY` in `.env`.

## Proposed Changes

### Phase 1: Project Scaffolding & Docker

---

#### [NEW] [docker-compose.yml](file:///Users/parjanya-heaven/Desktop/dodge-ai/docker-compose.yml)
Define 4 services:
- `db-graph`: Neo4j (ports 7474, 7687)
- `db-relational`: PostgreSQL (port 5432)
- `api`: FastAPI (port 8000), depends on both DBs
- `web`: React/Vite dev server (port 3000)

#### [NEW] [.env.example](file:///Users/parjanya-heaven/Desktop/dodge-ai/.env.example)
Template with all required env vars: `GOOGLE_API_KEY`, `NEO4J_URI`, `NEO4J_PASSWORD`, `POSTGRES_*`.

---

#### [NEW] [backend/Dockerfile](file:///Users/parjanya-heaven/Desktop/dodge-ai/backend/Dockerfile)
Python 3.11-slim image with FastAPI + dependencies.

#### [NEW] [backend/requirements.txt](file:///Users/parjanya-heaven/Desktop/dodge-ai/backend/requirements.txt)
`fastapi`, `uvicorn`, `neo4j`, `sqlalchemy`, `psycopg2-binary`, `langchain`, `langchain-google-genai`, `langchain-community`, `pydantic`, `python-dotenv`.

#### [NEW] [backend/app/main.py](file:///Users/parjanya-heaven/Desktop/dodge-ai/backend/app/main.py)
FastAPI app with CORS, lifespan for DB connections, health endpoint. Checks for `GOOGLE_API_KEY` on startup.

---

#### [NEW] [frontend/](file:///Users/parjanya-heaven/Desktop/dodge-ai/frontend/)
Scaffolded with `npm create vite@latest . -- --template react-ts`. Includes Dockerfile with Node dev server.

---

### Phase 2: Data Modeling & Ingestion

---

#### [NEW] [backend/app/models/graph_schema.py](file:///Users/parjanya-heaven/Desktop/dodge-ai/backend/app/models/graph_schema.py)

**Node types** (with key properties):
| Node Label | Key Fields | Source |
|---|---|---|
| `SalesOrder` | salesOrder, totalNetAmount, overallDeliveryStatus, creationDate | sales_order_headers |
| `SalesOrderItem` | salesOrder, salesOrderItem, material, netAmount, requestedQuantity | sales_order_items |
| `Delivery` | deliveryDocument, creationDate, overallGoodsMovementStatus | outbound_delivery_headers |
| `DeliveryItem` | deliveryDocument, deliveryDocumentItem, plant, actualDeliveryQuantity | outbound_delivery_items |
| `BillingDocument` | billingDocument, totalNetAmount, billingDocumentIsCancelled, creationDate | billing_document_headers |
| `BillingDocumentItem` | billingDocument, billingDocumentItem, material, netAmount | billing_document_items |
| `JournalEntry` | accountingDocument, companyCode, fiscalYear, amountInTransactionCurrency | journal_entry_items_accounts_receivable |
| `Payment` | accountingDocument, customer, amountInTransactionCurrency, clearingDate | payments_accounts_receivable |
| `Customer` | businessPartner, businessPartnerFullName, customer | business_partners |
| `Product` | product, productType, grossWeight, baseUnit | products |
| `Plant` | plant, plantName, salesOrganization | plants |

**Relationships**:
| Relationship | From → To | Join Key |
|---|---|---|
| `HAS_ITEM` | SalesOrder → SalesOrderItem | salesOrder |
| `CONTAINS_PRODUCT` | SalesOrderItem → Product | material = product |
| `FULFILLED_BY` | SalesOrderItem → DeliveryItem | salesOrder = referenceSdDocument |
| `BELONGS_TO_DELIVERY` | DeliveryItem → Delivery | deliveryDocument |
| `BILLED_AS` | DeliveryItem → BillingDocumentItem | deliveryDocument = referenceSdDocument |
| `BELONGS_TO_BILLING` | BillingDocumentItem → BillingDocument | billingDocument |
| `GENERATES_JOURNAL` | BillingDocument → JournalEntry | accountingDocument |
| `CLEARED_BY` | JournalEntry → Payment | clearingAccountingDocument |
| `SOLD_TO` | SalesOrder → Customer | soldToParty = businessPartner |
| `SHIPPED_FROM` | DeliveryItem → Plant | plant |
| `PRODUCED_AT` | Product → Plant | via product_plants |

#### [NEW] [backend/scripts/seed_data.py](file:///Users/parjanya-heaven/Desktop/dodge-ai/backend/scripts/seed_data.py)
Reads all JSONL files, creates nodes with `MERGE` (idempotent), creates relationships. Uses `neo4j` Python driver with batch transactions.

#### [NEW] [backend/app/models/chat_models.py](file:///Users/parjanya-heaven/Desktop/dodge-ai/backend/app/models/chat_models.py)
SQLAlchemy models: `ChatSession`, `ChatMessage` (role, content, timestamp, cypher_query, node_ids).

---

### Phase 3: GenAI Query Engine

---

#### [NEW] [backend/app/services/graph_chain.py](file:///Users/parjanya-heaven/Desktop/dodge-ai/backend/app/services/graph_chain.py)
- Uses `GraphCypherQAChain` from LangChain with Gemini 1.5 Flash
- Injects full graph schema as context
- System prompt: "You are Dodge AI, an expert in SAP Order-to-Cash flows..."
- Returns structured response with `answer`, `cypher_query`, and `node_ids`

#### [NEW] [backend/app/services/guardrails.py](file:///Users/parjanya-heaven/Desktop/dodge-ai/backend/app/services/guardrails.py)
Intent classifier that rejects off-topic queries (jokes, creative writing, general knowledge).
Uses keyword + LLM-based classification with a pre-check.

#### [NEW] [backend/app/routes/chat.py](file:///Users/parjanya-heaven/Desktop/dodge-ai/backend/app/routes/chat.py)
Endpoints:
- `POST /api/chat` — accepts query, returns AI answer + Cypher + node IDs
- `GET /api/chat/history` — returns chat history
- `GET /api/graph/data` — returns full graph for visualization
- `GET /api/graph/node/{id}` — returns node details + neighbors

---

### Phase 4: Frontend UI

---

#### [NEW] [frontend/src/App.tsx](file:///Users/parjanya-heaven/Desktop/dodge-ai/frontend/src/App.tsx)
Two-column layout: Sidebar (chat, 25%) + Graph Canvas (75%).

#### [NEW] [frontend/src/components/GraphCanvas.tsx](file:///Users/parjanya-heaven/Desktop/dodge-ai/frontend/src/components/GraphCanvas.tsx)
- Uses `react-force-graph-2d`
- Color-coded nodes by entity type
- Hover tooltips showing node metadata
- Click to expand/inspect nodes
- Highlighted nodes from query results (pulsing animation)

#### [NEW] [frontend/src/components/ChatSidebar.tsx](file:///Users/parjanya-heaven/Desktop/dodge-ai/frontend/src/components/ChatSidebar.tsx)
- Chat message list with user/AI bubbles
- Input field at bottom
- Word-by-word streaming response display
- Sample query cards for new sessions

#### [NEW] [frontend/src/index.css](file:///Users/parjanya-heaven/Desktop/dodge-ai/frontend/src/index.css)
Dark theme with glassmorphism panels, color-coded entity types, smooth transitions, and micro-animations.

---

### Phase 5: Integration & Polish

- Node highlighting: Backend returns `node_ids` → frontend pulses matching nodes
- Trace flow: Dedicated Cypher query returning the linear path for a billing document
- Expand/collapse: Click node → fetch neighbors from API → add to graph

---

### Phase 6: Docker Packaging

#### [MODIFY] [docker-compose.yml](file:///Users/parjanya-heaven/Desktop/dodge-ai/docker-compose.yml)
Add health checks for Neo4j/Postgres, `depends_on` with `condition: service_healthy`.

#### [NEW] [README.md](file:///Users/parjanya-heaven/Desktop/dodge-ai/README.md)
Setup instructions, architecture diagram, Text-to-Cypher strategy explanation.

---

## Verification Plan

### Automated Tests

1. **Docker services boot**:
   ```bash
   cd /Users/parjanya-heaven/Desktop/dodge-ai && docker-compose up --build -d
   docker-compose ps  # all 4 services healthy
   ```

2. **Backend API health**:
   ```bash
   curl http://localhost:8000/health
   # Expect: {"status": "ok"}
   ```

3. **Data seeding**:
   ```bash
   docker-compose exec api python scripts/seed_data.py
   # Verify node counts in Neo4j browser at localhost:7474
   ```

4. **Guardrails test**:
   ```bash
   curl -X POST http://localhost:8000/api/chat \
     -H "Content-Type: application/json" \
     -d '{"query": "Tell me a joke"}'
   # Expect: guardrail rejection response
   ```

5. **Query test**:
   ```bash
   curl -X POST http://localhost:8000/api/chat \
     -H "Content-Type: application/json" \
     -d '{"query": "Which products have the most billing documents?"}'
   # Expect: data-backed response with node IDs
   ```

### Browser Verification
- Open `http://localhost:3000` — graph renders with color-coded nodes
- Hover a node → metadata tooltip appears
- Type a query in chat → streamed AI response
- Queried nodes pulse/highlight in graph
- Sample query cards clickable and functional

### Manual Verification
- Type "Trace the full flow of billing document 90504248" and confirm the graph zooms to show the linear O2C path.

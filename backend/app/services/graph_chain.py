"""
Text-to-Cypher engine using LangChain + Gemini + Neo4j.

Architecture:
  1. User query → Gemini generates Cypher via a schema-aware system prompt
  2. Cypher → executed against Neo4j
  3. Raw results → Gemini synthesises a natural-language answer
  4. Extracted node IDs are returned for graph highlighting
"""

import json
import os
import re
from typing import Any

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.graphs import Neo4jGraph
from langchain.chains import GraphCypherQAChain
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from app.models.graph_schema import get_schema_description

# ── Singleton references (initialised lazily) ──────────────────────
_graph: Neo4jGraph | None = None
_chain: GraphCypherQAChain | None = None

# ── System prompt for Cypher generation ────────────────────────────
_CYPHER_SYSTEM = """\
You are Dodge AI, an expert in SAP Order-to-Cash (O2C) business processes \
and Neo4j Cypher. Your task is to generate ONLY valid Cypher queries.

RULES:
1. Use ONLY the node labels, relationship types, and property names from the schema below.
2. Always use the correct property names exactly as defined — they are camelCase.
3. For string matching, use toLower() for case-insensitive comparisons.
4. Use LIMIT to cap results (default 25 unless the user asks for more).
5. When the user asks for a "trace" or "flow", return the full O2C path.
6. Return ONLY the Cypher query — no explanations, no markdown.
7. Never use labels or relationships not listed in the schema.
8. For aggregate queries, always alias computed columns clearly.
9. Node IDs in Neo4j are accessed with id(node) or elementId(node).
10. When filtering by specific document numbers, match them as strings.

{schema}
"""

_QA_SYSTEM = """\
You are Dodge AI, an SAP Order-to-Cash analytics assistant. Given the \
user's question and the query results from the graph database, provide \
a clear, concise, and helpful answer.

RULES:
1. Summarize the data in natural language — don't just dump raw JSON.
2. When presenting numbers, format them nicely (e.g., currency with 2 decimals).
3. Use bullet points or tables when listing multiple items.
4. If the result set is empty, say so clearly and suggest an alternative query.
5. Reference specific document numbers, customer names, or product IDs from the results.
6. Keep responses professional and data-focused.
"""


def _get_graph() -> Neo4jGraph:
    """Lazily initialize the Neo4jGraph wrapper."""
    global _graph
    if _graph is None:
        _graph = Neo4jGraph(
            url=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            username=os.getenv("NEO4J_USER", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", "dodge_ai_2024"),
        )
    return _graph


def _get_chain() -> GraphCypherQAChain:
    """Lazily initialize the GraphCypherQAChain."""
    global _chain
    if _chain is not None:
        return _chain

    graph = _get_graph()
    schema_text = get_schema_description()

    cypher_llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=0,
        convert_system_message_to_human=True,
    )

    qa_llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=0.3,
        convert_system_message_to_human=True,
    )

    cypher_prompt = ChatPromptTemplate.from_messages([
        ("system", _CYPHER_SYSTEM.format(schema=schema_text)),
        ("human", "{query}"),
    ])

    qa_prompt = ChatPromptTemplate.from_messages([
        ("system", _QA_SYSTEM),
        ("human",
         "User Question: {query}\n\n"
         "Cypher Query Used:\n```\n{context}\n```\n\n"
         "Query Results:\n{context}"),
    ])

    _chain = GraphCypherQAChain.from_llm(
        llm=qa_llm,
        cypher_llm=cypher_llm,
        graph=graph,
        cypher_prompt=cypher_prompt,
        qa_prompt=qa_prompt,
        verbose=True,
        return_intermediate_steps=True,
        validate_cypher=True,
        allow_dangerous_requests=True,
        top_k=50,
    )
    return _chain


def _extract_node_ids(result_data: Any) -> list[str]:
    """
    Extract recognizable entity IDs from Cypher results to highlight
    on the frontend graph. Looks for known primary-key field names.
    """
    pk_fields = {
        "salesOrder", "deliveryDocument", "billingDocument",
        "accountingDocument", "businessPartner", "product", "plant",
        "salesOrderItem", "deliveryDocumentItem", "billingDocumentItem",
    }
    ids = set()

    def _walk(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in pk_fields and v is not None:
                    ids.add(str(v))
                else:
                    _walk(v)
        elif isinstance(obj, list):
            for item in obj:
                _walk(item)

    _walk(result_data)
    return list(ids)


async def query_graph(user_query: str) -> dict:
    """
    End-to-end: natural language → Cypher → Neo4j → natural language answer.

    Returns:
        {
            "answer": str,
            "cypher_query": str,
            "raw_results": list,
            "node_ids": list[str],
        }
    """
    chain = _get_chain()

    try:
        result = await chain.ainvoke({"query": user_query})
    except Exception as e:
        error_msg = str(e)
        # Try to provide a useful error message
        if "syntax" in error_msg.lower() or "cypher" in error_msg.lower():
            return {
                "answer": (
                    "⚠️ I generated an invalid Cypher query. "
                    "Could you rephrase your question? "
                    f"Error detail: {error_msg[:200]}"
                ),
                "cypher_query": "",
                "raw_results": [],
                "node_ids": [],
            }
        raise

    # Extract intermediate steps
    intermediate = result.get("intermediate_steps", [])
    cypher_query = ""
    raw_results = []

    if intermediate:
        # intermediate_steps is typically [{"query": "..."}, {"context": [...]}]
        for step in intermediate:
            if isinstance(step, dict):
                if "query" in step:
                    cypher_query = step["query"]
                if "context" in step:
                    raw_results = step["context"]
            elif isinstance(step, str) and step.strip().upper().startswith("MATCH"):
                cypher_query = step

    answer = result.get("result", "I couldn't find an answer for that query.")
    node_ids = _extract_node_ids(raw_results)

    return {
        "answer": answer,
        "cypher_query": cypher_query,
        "raw_results": raw_results if isinstance(raw_results, list) else [],
        "node_ids": node_ids,
    }


async def get_full_graph(limit: int = 300) -> dict:
    """
    Fetch a subset of the graph for initial visualization.
    Returns nodes and links in a format consumable by react-force-graph.
    """
    graph = _get_graph()

    # Fetch nodes of each type with a limit
    nodes_query = """
    CALL {
        MATCH (n:SalesOrder) RETURN n, labels(n)[0] AS label LIMIT 30
        UNION ALL
        MATCH (n:SalesOrderItem) RETURN n, labels(n)[0] AS label LIMIT 50
        UNION ALL
        MATCH (n:Delivery) RETURN n, labels(n)[0] AS label LIMIT 30
        UNION ALL
        MATCH (n:DeliveryItem) RETURN n, labels(n)[0] AS label LIMIT 50
        UNION ALL
        MATCH (n:BillingDocument) RETURN n, labels(n)[0] AS label LIMIT 30
        UNION ALL
        MATCH (n:BillingDocumentItem) RETURN n, labels(n)[0] AS label LIMIT 50
        UNION ALL
        MATCH (n:JournalEntry) RETURN n, labels(n)[0] AS label LIMIT 20
        UNION ALL
        MATCH (n:Payment) RETURN n, labels(n)[0] AS label LIMIT 20
        UNION ALL
        MATCH (n:Customer) RETURN n, labels(n)[0] AS label LIMIT 10
        UNION ALL
        MATCH (n:Product) RETURN n, labels(n)[0] AS label LIMIT 10
        UNION ALL
        MATCH (n:Plant) RETURN n, labels(n)[0] AS label LIMIT 10
    }
    RETURN elementId(n) AS id, label, properties(n) AS props
    """

    # Fetch relationships between those nodes
    rels_query = """
    MATCH (a)-[r]->(b)
    WITH a, r, b, type(r) AS relType LIMIT $limit
    RETURN elementId(a) AS source, elementId(b) AS target, type(r) AS type
    """

    try:
        nodes_result = graph.query(nodes_query)
        rels_result = graph.query(rels_query, params={"limit": limit})
    except Exception as e:
        print(f"⚠️ Graph fetch error: {e}")
        return {"nodes": [], "links": []}

    # Build node list
    node_ids_set = set()
    nodes = []
    for record in nodes_result:
        nid = record["id"]
        if nid not in node_ids_set:
            node_ids_set.add(nid)
            props = record.get("props", {})
            # Create a display name from primary key fields
            label = record["label"]
            display = _get_display_name(label, props)
            nodes.append({
                "id": nid,
                "label": label,
                "name": display,
                "properties": _clean_props(props),
            })

    # Build links (only between nodes we have)
    links = []
    for record in rels_result:
        if record["source"] in node_ids_set and record["target"] in node_ids_set:
            links.append({
                "source": record["source"],
                "target": record["target"],
                "type": record["type"],
            })

    return {"nodes": nodes, "links": links}


async def get_node_neighbors(node_id: str) -> dict:
    """Fetch a node and its immediate neighbors for expand-on-click."""
    graph = _get_graph()

    query = """
    MATCH (n) WHERE elementId(n) = $nodeId
    OPTIONAL MATCH (n)-[r]-(m)
    RETURN
        elementId(n) as centerNodeId,
        labels(n)[0] as centerLabel,
        properties(n) as centerProps,
        collect(DISTINCT {
            id: elementId(m),
            label: labels(m)[0],
            props: properties(m),
            rel_type: type(r),
            direction: CASE WHEN startNode(r) = n THEN 'outgoing' ELSE 'incoming' END
        }) as neighbors
    """

    try:
        result = graph.query(query, params={"nodeId": node_id})
    except Exception:
        return {"node": None, "neighbors": []}

    if not result:
        return {"node": None, "neighbors": []}

    record = result[0]
    center_props = record.get("centerProps", {})
    center_label = record.get("centerLabel", "")

    node = {
        "id": record["centerNodeId"],
        "label": center_label,
        "name": _get_display_name(center_label, center_props),
        "properties": _clean_props(center_props),
    }

    neighbors = []
    for n in record.get("neighbors", []):
        if n.get("id") is None:
            continue
        n_label = n.get("label", "")
        n_props = n.get("props", {})
        neighbors.append({
            "id": n["id"],
            "label": n_label,
            "name": _get_display_name(n_label, n_props),
            "properties": _clean_props(n_props),
            "rel_type": n.get("rel_type", ""),
            "direction": n.get("direction", ""),
        })

    return {"node": node, "neighbors": neighbors}


def _get_display_name(label: str, props: dict) -> str:
    """Create a human-readable display name for a node."""
    pk_map = {
        "SalesOrder": "salesOrder",
        "SalesOrderItem": ("salesOrder", "salesOrderItem"),
        "Delivery": "deliveryDocument",
        "DeliveryItem": ("deliveryDocument", "deliveryDocumentItem"),
        "BillingDocument": "billingDocument",
        "BillingDocumentItem": ("billingDocument", "billingDocumentItem"),
        "JournalEntry": "accountingDocument",
        "Payment": "accountingDocument",
        "Customer": "businessPartnerFullName",
        "Product": "product",
        "Plant": "plantName",
    }

    pk = pk_map.get(label)
    if pk is None:
        return label

    if isinstance(pk, tuple):
        parts = [str(props.get(k, "?")) for k in pk]
        return f"{label} {'/'.join(parts)}"

    value = props.get(pk, "?")
    return f"{label} {value}" if label not in ("Customer", "Plant") else str(value)


def _clean_props(props: dict) -> dict:
    """Clean property values for JSON serialization."""
    cleaned = {}
    for k, v in props.items():
        if v is None:
            continue
        if isinstance(v, (int, float, str, bool)):
            cleaned[k] = v
        else:
            cleaned[k] = str(v)
    return cleaned

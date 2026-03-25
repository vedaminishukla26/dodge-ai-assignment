"""
Guardrails module – filters out off-topic queries before they reach the
expensive Text-to-Cypher pipeline.

Strategy:
  1. Fast keyword pre-check (regex) for obviously off-topic phrases.
  2. LLM-based intent classification as fallback for ambiguous queries.
"""

import os
import re

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

# ── Keywords that strongly indicate off-topic queries ───────────────
_OFF_TOPIC_PATTERNS = [
    r"\b(joke|funny|humor|laugh)\b",
    r"\b(poem|poetry|sonnet|haiku|limerick)\b",
    r"\b(recipe|cook|bake|food|meal)\b",
    r"\b(weather|forecast|temperature)\b",
    r"\b(movie|film|tv show|series|netflix)\b",
    r"\b(song|music|lyrics|album|artist)\b",
    r"\b(game|play|sport|score)\b",
    r"\b(celebrity|famous|gossip)\b",
    r"\b(story|fiction|novel|fairy tale)\b",
    r"\b(who is the president|capital of|population of)\b",
    r"\b(meaning of life|philosophy|religion)\b",
    r"\b(code|program|python|javascript|html)\b",
    r"\b(translate|translation)\b",
    r"\b(math problem|calculate|equation|algebra)\b",
]

_OFF_TOPIC_RE = re.compile("|".join(_OFF_TOPIC_PATTERNS), re.IGNORECASE)

# ── Keywords that strongly indicate on-topic queries ────────────────
_ON_TOPIC_PATTERNS = [
    r"\b(sales\s*order|order|SO)\b",
    r"\b(delivery|shipment|outbound)\b",
    r"\b(billing|invoice|bill)\b",
    r"\b(payment|paid|receivable|clearing)\b",
    r"\b(journal|accounting|posting)\b",
    r"\b(customer|partner|sold.?to)\b",
    r"\b(product|material|item)\b",
    r"\b(plant|warehouse|storage)\b",
    r"\b(SAP|O2C|order.?to.?cash)\b",
    r"\b(cypher|graph|node|relationship)\b",
    r"\b(net\s*amount|total|quantity|weight|currency)\b",
    r"\b(status|cancelled|blocked|overdue)\b",
    r"\b(trace|flow|pipeline|process)\b",
]

_ON_TOPIC_RE = re.compile("|".join(_ON_TOPIC_PATTERNS), re.IGNORECASE)

_CLASSIFIER_PROMPT = """\
You are a strict intent classifier for an SAP Order-to-Cash (O2C) \
data analytics system. Your ONLY job is to decide whether the user's \
question is about SAP O2C data (sales orders, deliveries, billing, \
payments, journal entries, customers, products, plants, etc.).

Reply with EXACTLY one word:
  ON_TOPIC   — if the question relates to SAP O2C data or business analytics
  OFF_TOPIC  — if the question is unrelated (jokes, recipes, general knowledge, etc.)

Do NOT explain. Just reply with one word."""

_REJECTION_MESSAGE = (
    "🚫 I'm **Dodge AI**, an SAP Order-to-Cash analytics assistant. "
    "I can only answer questions about sales orders, deliveries, billing, "
    "payments, journal entries, customers, products, and plants.\n\n"
    "Try asking something like:\n"
    "- *\"Which customers have the highest total billing amount?\"*\n"
    "- *\"Show me all sales orders for product TG11\"*\n"
    "- *\"Trace the full O2C flow for sales order 1\"*"
)


def _keyword_precheck(query: str) -> str | None:
    """
    Returns 'on_topic', 'off_topic', or None (ambiguous → needs LLM).
    """
    has_on = bool(_ON_TOPIC_RE.search(query))
    has_off = bool(_OFF_TOPIC_RE.search(query))

    if has_on and not has_off:
        return "on_topic"
    if has_off and not has_on:
        return "off_topic"
    return None  # ambiguous – ask the LLM


async def check_guardrail(query: str) -> dict:
    """
    Returns:
        {"allowed": True}              — if on-topic
        {"allowed": False, "message": "..."} — if off-topic
    """
    # Step 1: fast keyword check
    verdict = _keyword_precheck(query)
    if verdict == "on_topic":
        return {"allowed": True}
    if verdict == "off_topic":
        return {"allowed": False, "message": _REJECTION_MESSAGE}

    # Step 2: LLM classification for ambiguous queries
    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            temperature=0,
            max_output_tokens=10,
        )
        response = await llm.ainvoke([
            SystemMessage(content=_CLASSIFIER_PROMPT),
            HumanMessage(content=query),
        ])
        answer = response.content.strip().upper()
        if "OFF" in answer:
            return {"allowed": False, "message": _REJECTION_MESSAGE}
    except Exception:
        # If LLM fails, allow the query through (fail-open for classification)
        pass

    return {"allowed": True}

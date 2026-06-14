from typing import TypedDict
from langgraph.graph import StateGraph, END
from langchain_groq import ChatGroq
from dotenv import load_dotenv

import hashlib
import os

load_dotenv()

# ==================================================
# LLM
# ==================================================

llm = ChatGroq(
    groq_api_key=os.getenv("GROQ_API_KEY"),
    model_name="llama-3.3-70b-versatile",
    temperature=0
)

# ==================================================
# STATE
# ==================================================

class SupportState(TypedDict, total=False):

    customer_name: str
    question: str

    department: str
    priority: str
    sentiment: str
    customer_type: str

    ticket_id: str
    confidence: str

    tech_response: str
    billing_response: str
    sales_response: str

    reviewer_response: str
    answer: str

    summary: str

    escalation: bool
    ticket_closed: bool


# ==================================================
# HELPERS
# ==================================================

def generate_customer_ticket(name: str):

    ticket = hashlib.md5(
        name.strip().lower().encode()
    ).hexdigest()[:6].upper()

    return f"CUST-{ticket}"


def is_ticket_closure(question):

    keywords = [
        "resolved",
        "issue resolved",
        "problem solved",
        "fixed",
        "close ticket",
        "close my ticket",
        "thank you",
        "thanks",
        "done",
        "working now"
    ]

    question = question.lower()

    return any(
        word in question
        for word in keywords
    )


# ==================================================
# CLASSIFIER AGENT
# ==================================================

def classifier_agent(state):

    response = llm.invoke(
        f"""
You are a Customer Support Classifier.

Customer Question:
{state['question']}

Return ONLY in this format:

Department: Tech/Billing/Sales/General
Priority: High/Medium
Sentiment: Positive/Neutral/Negative

Rules:

Tech:
- login
- password
- access
- bug
- error
- website
- app
- crash
- account

Billing:
- refund
- payment
- charged
- invoice
- subscription
- renewal

Sales:
- pricing
- plans
- demo
- feature
- enterprise
- purchase
- quote

Priority:
High if urgent/critical/asap/immediately

Sentiment:
Negative if angry/frustrated/upset
Positive if happy/love/great
Else Neutral
"""
    )

    text = response.content

    department = "General"
    priority = "Medium"
    sentiment = "Neutral"

    for line in text.splitlines():

        if line.lower().startswith("department:"):
            department = line.split(":", 1)[1].strip()

        elif line.lower().startswith("priority:"):
            priority = line.split(":", 1)[1].strip()

        elif line.lower().startswith("sentiment:"):
            sentiment = line.split(":", 1)[1].strip()

    return {
        "department": department,
        "priority": priority,
        "sentiment": sentiment,
        "customer_type":
            "VIP"
            if len(state["question"]) > 120
            else "Standard",

        "ticket_id":
            generate_customer_ticket(
                state["customer_name"]
            ),

        "confidence": "AI Generated"
    }


# ==================================================
# TECH AGENT
# ==================================================

def tech_agent(state):

    response = llm.invoke(
        f"""
You are a Senior Technical Support Engineer.

Customer:
{state['customer_name']}

Issue:
{state['question']}

Provide:

1. Technical analysis
2. Possible root cause
3. Troubleshooting steps
4. Recommendation
"""
    )

    return {
        "tech_response": response.content
    }


# ==================================================
# BILLING AGENT
# ==================================================

def billing_agent(state):

    response = llm.invoke(
        f"""
You are a Senior Billing Specialist.

Customer:
{state['customer_name']}

Question:
{state['question']}

Provide:

1. Billing analysis
2. Possible payment issues
3. Refund guidance
4. Subscription recommendations
"""
    )

    return {
        "billing_response": response.content
    }


# ==================================================
# SALES AGENT
# ==================================================

def sales_agent(state):

    response = llm.invoke(
        f"""
You are a Senior Sales Consultant.

Customer:
{state['customer_name']}

Question:
{state['question']}

Provide:

1. Sales perspective
2. Product recommendations
3. Upgrade opportunities
4. Relevant plans/features
"""
    )

    return {
        "sales_response": response.content
    }


# ==================================================
# REVIEWER AGENT
# ==================================================

def reviewer_agent(state):

    response = llm.invoke(
        f"""
You are a Senior Support Manager.

Your job is to review the outputs
from multiple specialist agents and
produce ONE final answer.

Customer Question:
{state['question']}

==================================
TECH AGENT
==================================

{state.get('tech_response', '')}

==================================
BILLING AGENT
==================================

{state.get('billing_response', '')}

==================================
SALES AGENT
==================================

{state.get('sales_response', '')}

==================================

Instructions:

1. Identify which agent responses
   are relevant.

2. Ignore irrelevant information.

3. Merge useful insights.

4. Create ONE professional response.

5. Keep answer customer friendly.

6. End with a follow-up question.
"""
    )

    return {
        "reviewer_response": response.content,
        "answer": response.content
    }


# ==================================================
# SUMMARY AGENT
# ==================================================

def summary_agent(state):

    response = llm.invoke(
        f"""
Summarize this support request
in one concise sentence:

Question:
{state['question']}

Final Response:
{state['answer']}
"""
    )

    return {
        "summary": response.content
    }


# ==================================================
# TICKET CLOSURE
# ==================================================

def closure_agent(state):

    if is_ticket_closure(
        state["question"]
    ):

        return {

            "ticket_closed": True,

            "answer":
f"""
✅ Ticket Closed Successfully

Ticket ID:
{state['ticket_id']}

We're happy your issue
has been resolved.

Thank you for contacting support.

Feel free to reach out again
if you need assistance.
"""
        }

    return {
        "ticket_closed": False
    }


# ==================================================
# ESCALATION AGENT
# ==================================================

def escalation_agent(state):

    if state.get("ticket_closed"):

        return state

    escalate = (
        state["priority"] == "High"
        or
        state["sentiment"] == "Negative"
    )

    answer = state["answer"]

    if escalate:

        answer += """

--------------------------------

🚨 Escalation Notice

Your request has been flagged for human-agent review due to priority or sentiment level.
"""

    return {
        "answer": answer,
        "escalation": escalate
    }


# ==================================================
# GRAPH
# ==================================================

graph = StateGraph(SupportState)

graph.add_node(
    "classifier",
    classifier_agent
)

graph.add_node(
    "tech_agent",
    tech_agent
)

graph.add_node(
    "billing_agent",
    billing_agent
)

graph.add_node(
    "sales_agent",
    sales_agent
)

graph.add_node(
    "reviewer",
    reviewer_agent
)

graph.add_node(
    "summary",
    summary_agent
)

graph.add_node(
    "closure",
    closure_agent
)

graph.add_node(
    "escalation",
    escalation_agent
)

# ENTRY

graph.set_entry_point(
    "classifier"
)

# ==========================================
# PARALLEL FAN OUT
# ==========================================

graph.add_edge(
    "classifier",
    "tech_agent"
)

graph.add_edge(
    "classifier",
    "billing_agent"
)

graph.add_edge(
    "classifier",
    "sales_agent"
)

# ==========================================
# FAN IN
# ==========================================

graph.add_edge(
    "tech_agent",
    "reviewer"
)

graph.add_edge(
    "billing_agent",
    "reviewer"
)

graph.add_edge(
    "sales_agent",
    "reviewer"
)

# ==========================================
# FINAL FLOW
# ==========================================

graph.add_edge(
    "reviewer",
    "summary"
)

graph.add_edge(
    "summary",
    "closure"
)

graph.add_edge(
    "closure",
    "escalation"
)

graph.add_edge(
    "escalation",
    END
)

support_app = graph.compile()
import os
from typing import TypedDict
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, END

load_dotenv()

llm = ChatGroq(
    groq_api_key=os.getenv("GROQ_API_KEY"),
    model_name="llama-3.1-8b-instant",
    temperature=0.4,
)

class DebateState(TypedDict, total=False):
    topic: str
    pro: str
    opp: str
    verdict: str

# -------------------------
# PROMPTS
# -------------------------
def pro_prompt(topic: str) -> str:
    return f"You are a strong debater supporting the given topic.\nRules:\n- Give logical arguments\n- Stay structured (point-wise)\n\nTopic: {topic}\n"

def opp_prompt(topic: str, pro_text: str) -> str:
    return f"You are a critical opponent debater.\nRules:\n- Attack weak points in the pro argument\n- Provide counterexamples\n\nTopic: {topic}\n\nProponent argument:\n{pro_text}\n"

def judge_prompt(topic: str, pro_text: str, opp_text: str) -> str:
    return f"You are an unbiased debate judge.\nEvaluate based on logic, evidence, and clarity.\n\nTopic: {topic}\n\nProponent:\n{pro_text}\n\nOpponent:\n{opp_text}\n\nReturn:\n1. Winner\n2. Score (Pro vs Opp out of 10)\n3. Reasoning\n"

# -------------------------
# NODES
# -------------------------
def pro_node(state: DebateState):
    result = llm.invoke(pro_prompt(state["topic"]))
    return {"pro": result.content}

def opp_node(state: DebateState):
    result = llm.invoke(opp_prompt(state["topic"], state.get("pro", "")))
    return {"opp": result.content}

def judge_node(state: DebateState):
    result = llm.invoke(judge_prompt(state["topic"], state.get("pro", ""), state.get("opp", "")))
    return {"verdict": result.content}

# -------------------------
# BUILD GRAPH
# -------------------------
def build_graph():
    workflow = StateGraph(DebateState)
    
    workflow.add_node("pro", pro_node)
    workflow.add_node("opp", opp_node)
    workflow.add_node("judge", judge_node)
    
    workflow.set_entry_point("pro")
    workflow.add_edge("pro", "opp")
    workflow.add_edge("opp", "judge")
    workflow.add_edge("judge", END)
    
    return workflow.compile()
import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()

llm = ChatGroq(
    groq_api_key=os.getenv("GROQ_API_KEY"),
    model_name="llama-3.3-70b-versatile",
    temperature=0.4,
)


def run_llm(prompt: str):
    """Non-streaming helper for LangGraph (clean state updates)"""
    return llm.invoke(prompt).content


def stream_llm(prompt: str):
    """Optional streaming (UI can still use SSE if needed)"""
    for chunk in llm.stream(prompt):
        if chunk.content:
            yield chunk.content
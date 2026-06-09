from groq import Groq
from dotenv import load_dotenv
import os

load_dotenv()

client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)

def research_agent(query):

    prompt = f"""
    You are an expert Research Agent.
    Research the topic below in detail:

    {query}

    Give:
    - Overview
    - Key Facts
    - Latest Trends
    - Important Insights
    
    Return the response in proper Markdown format.
    Use headings, bullet points, and code blocks where appropriate.
    """

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role":"user","content":prompt}
        ]
    )

    return response.choices[0].message.content
from groq import Groq
from dotenv import load_dotenv
import os

load_dotenv()

client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)

def coding_agent(query):

    prompt = f"""
    You are a Senior Software Engineer.
    Generate code for:

    {query}

    Include:
    - Explanation
    - Full Code
    - Best Practices
    
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
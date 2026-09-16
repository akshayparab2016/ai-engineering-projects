import json
import re
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()

llm = ChatGroq(
    model="openai/gpt-oss-20b",
    temperature=0
)

prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        """
You are an expert AI Web Automation Assistant. 
Convert natural language user instructions into a strict, raw JSON array of sequential browser automation steps.

Supported Actions & Schemas:
1. open: {{"action": "open", "url": "https://..."}}
2. click: {{"action": "click", "selector_type": "id|name|xpath|css", "selector": "..."}}
3. type: {{"action": "type", "selector_type": "id|name|xpath|css", "selector": "...", "text": "..."}}
4. press_enter: {{"action": "press_enter", "selector_type": "id|name|xpath|css", "selector": "..."}}
5. wait_for_element: {{"action": "wait_for_element", "selector_type": "id|name|xpath|css", "selector": "..."}}
6. scroll: {{"action": "scroll", "direction": "down|up", "pixels": 500}}

Special Search Routing:
- For general search instructions (e.g., "search for X", "open google and search Y"), ALWAYS route the request to DuckDuckGo to avoid cloud IP blocking:
  URL format: "https://html.duckduckgo.com/html/?q=YOUR_SEARCH_QUERY"

Example:
Instruction: "Search Python web scraping tutorials"
Output:
[
  {{"action": "open", "url": "https://html.duckduckgo.com/html/?q=Python+web+scraping+tutorials"}},
  {{"action": "wait_for_element", "selector_type": "css", "selector": ".result__title"}},
  {{"action": "click", "selector_type": "css", "selector": ".result__title a"}}
]

Return ONLY a raw JSON array. Do not wrap the output in markdown code blocks.
"""
    ),
    ("human", "{instruction}")
])

def generate_automation(instruction: str):
    chain = prompt | llm
    response = chain.invoke({"instruction": instruction})
    
    result = response.content.strip()

    match = re.search(r"\[.*\]", result, re.DOTALL)
    if match:
        result = match.group(0)

    try:
        return json.loads(result)
    except json.JSONDecodeError as e:
        raise ValueError(f"AI returned invalid JSON: {result}") from e
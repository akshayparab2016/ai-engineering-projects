import json
import os
import re

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

load_dotenv()

llm = ChatGroq(
    model=os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"),
    temperature=0,
)

# NOTE: literal curly braces inside the template must be doubled ({{ }}).
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
7. wait: {{"action": "wait", "seconds": 2}}
8. extract_text: {{"action": "extract_text", "selector_type": "id|name|xpath|css", "selector": "...", "limit": 5}}

Rules:
- The first step MUST be an "open" step with a full https:// URL.
- Use "extract_text" whenever the user asks to read, get, list, collect or extract text from a page.
- After a step that loads a new page (open, click, press_enter), add a "wait_for_element" for the element the next step needs.
- Prefer id or name selectors, then short css selectors. Never invent long or fragile selectors.
- Keep the plan as short as possible (at most 20 steps).

Special Search Routing:
- For general search instructions (e.g., "search for X", "open google and search Y"), ALWAYS route the request to DuckDuckGo to avoid cloud IP blocking:
  URL format: "https://html.duckduckgo.com/html/?q=YOUR_SEARCH_QUERY" (URL-encode the query, using + for spaces)

Known sites (use these selectors):
- Amazon (https://www.amazon.com): search box id "twotabsearchtextbox"; result links css "[data-component-type='s-search-result'] h2 a"
- Wikipedia (https://en.wikipedia.org): search box name "search"
- Hacker News (https://news.ycombinator.com): story titles css ".titleline > a"
- practicetestautomation.com login page: username id "username", password id "password", submit button id "submit"

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

chain = prompt | llm


def _content_text(content) -> str:
    """Normalises a model response (or streamed chunk) content to a plain string."""
    if isinstance(content, list):
        content = "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )
    return str(content or "")


def _extract_json_array(raw: str) -> list:
    """Pulls a JSON array out of the model output, even if it was wrapped in text."""
    text = raw.strip()
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        text = match.group(0)

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"the model returned invalid JSON ({e.msg} at position {e.pos})") from e

    if not isinstance(data, list):
        raise ValueError("the model did not return a JSON array")
    return data


def stream_automation(instruction: str, validator=None, max_attempts: int = 2):
    """
    Streams the plan while the model writes it.

    Yields dicts:
      {"type": "chunk", "text": "..."}     a piece of the raw model output
      {"type": "retry", "message": "..."}  the answer was rejected, the model tries again
      {"type": "plan",  "steps": [...]}    the final, validated plan (always the last event)

    `validator` is an optional callable that receives the parsed steps and returns
    the cleaned steps (or raises ValueError).
    """
    last_error = None

    for attempt in range(max_attempts):
        text = instruction
        if last_error:
            text = (
                f"{instruction}\n\n"
                f"Your previous answer was rejected: {last_error}.\n"
                "Return a corrected raw JSON array only."
            )

        parts = []
        for chunk in chain.stream({"instruction": text}):
            piece = _content_text(chunk.content)
            if piece:
                parts.append(piece)
                yield {"type": "chunk", "text": piece}

        try:
            steps = _extract_json_array("".join(parts))
            if validator:
                steps = validator(steps)
            yield {"type": "plan", "steps": steps}
            return
        except ValueError as e:
            last_error = str(e)
            if attempt + 1 < max_attempts:
                yield {"type": "retry", "message": last_error}

    raise ValueError(f"Could not build a valid action plan: {last_error}")


def generate_automation(instruction: str, validator=None, max_attempts: int = 2):
    """Non-streaming version: returns only the final validated plan."""
    steps = None
    for event in stream_automation(instruction, validator, max_attempts):
        if event["type"] == "plan":
            steps = event["steps"]
    return steps

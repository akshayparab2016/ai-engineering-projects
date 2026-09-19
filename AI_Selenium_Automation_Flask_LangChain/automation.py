import ipaddress
import os
import time
from urllib.parse import urlparse

from selenium import webdriver
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    ElementNotInteractableException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium_stealth import stealth

# ---------------------------------------------------------------------------
# Configuration (override through environment variables)
# ---------------------------------------------------------------------------
HEADLESS = os.getenv("HEADLESS", "true").lower() != "false"
STEP_TIMEOUT = int(os.getenv("STEP_TIMEOUT", "15"))
PAGE_LOAD_TIMEOUT = int(os.getenv("PAGE_LOAD_TIMEOUT", "30"))
ALLOW_LOCAL_URLS = os.getenv("ALLOW_LOCAL_URLS", "false").lower() == "true"
CHROME_BIN = os.getenv("CHROME_BIN")
CHROME_DEBUG_PORT = os.getenv("CHROME_DEBUG_PORT")  # only needed on some Docker setups

MAX_STEPS = 30

# ---------------------------------------------------------------------------
# Plan schema
# ---------------------------------------------------------------------------
ALLOWED_ACTIONS = {
    "open",
    "click",
    "type",
    "press_enter",
    "wait_for_element",
    "scroll",
    "wait",
    "extract_text",
}
SELECTOR_ACTIONS = {"click", "type", "press_enter", "wait_for_element", "extract_text"}

# selector_type (as written in the plan) -> Selenium locator strategy
BY_MAP = {
    "id": By.ID,
    "name": By.NAME,
    "xpath": By.XPATH,
    "css": By.CSS_SELECTOR,
    "class_name": By.CLASS_NAME,
    "tag_name": By.TAG_NAME,
    "link_text": By.LINK_TEXT,
}
# selector_type -> attribute name on `By`, used when generating the standalone script
BY_CODE = {
    "id": "ID",
    "name": "NAME",
    "xpath": "XPATH",
    "css": "CSS_SELECTOR",
    "class_name": "CLASS_NAME",
    "tag_name": "TAG_NAME",
    "link_text": "LINK_TEXT",
}
SELECTOR_ALIASES = {
    "css_selector": "css",
    "cssselector": "css",
    "class": "class_name",
    "classname": "class_name",
    "tag": "tag_name",
    "tagname": "tag_name",
    "linktext": "link_text",
}

BLOCKED_HOSTS = {"localhost", "0.0.0.0", "metadata.google.internal"}


def _to_number(value, default, low, high, cast=float):
    try:
        number = cast(value)
    except (TypeError, ValueError):
        number = default
    return max(low, min(high, number))


def normalize_selector_type(value):
    key = str(value or "css").strip().lower().replace("-", "_").replace(" ", "_")
    key = SELECTOR_ALIASES.get(key, key)
    if key not in BY_MAP:
        raise ValueError(f"unsupported selector_type '{value}'")
    return key


def normalize_url(value):
    """Only http(s) URLs to public hosts are allowed (the plan comes from an LLM)."""
    url = str(value or "").strip()
    if not url:
        raise ValueError("an 'open' step needs a url")
    if "://" not in url:
        url = "https://" + url

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError(f"only http(s) URLs are allowed, got '{url}'")

    if not ALLOW_LOCAL_URLS:
        host = parsed.hostname.lower()
        if host in BLOCKED_HOSTS or host.endswith((".local", ".internal", ".localhost")):
            raise ValueError(f"local or internal address is not allowed: '{host}'")
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            ip = None  # a normal hostname
        if ip and (ip.is_private or ip.is_loopback or ip.is_link_local
                   or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
            raise ValueError(f"private IP addresses are not allowed: '{host}'")

    return url


def validate_steps(steps):
    """
    Checks a plan (from the AI or from the editable JSON box) and returns a clean copy.
    Raises ValueError with a readable message when something is wrong.
    """
    if not isinstance(steps, list) or not steps:
        raise ValueError("the plan must be a non-empty JSON array of steps")
    if len(steps) > MAX_STEPS:
        raise ValueError(f"the plan has {len(steps)} steps, the maximum is {MAX_STEPS}")

    clean = []
    for i, raw in enumerate(steps, start=1):
        if not isinstance(raw, dict):
            raise ValueError(f"step {i} must be a JSON object")

        action = str(raw.get("action", "")).strip().lower()
        if action not in ALLOWED_ACTIONS:
            raise ValueError(f"step {i} has an unsupported action '{action}'")
        if i == 1 and action != "open":
            raise ValueError("the first step must be an 'open' step")

        step = {"action": action}
        try:
            if action == "open":
                step["url"] = normalize_url(raw.get("url"))

            elif action in SELECTOR_ACTIONS:
                selector = str(raw.get("selector", "")).strip()
                if not selector:
                    raise ValueError("a selector is required")
                step["selector_type"] = normalize_selector_type(raw.get("selector_type"))
                step["selector"] = selector
                if action == "type":
                    step["text"] = str(raw.get("text", ""))
                if action == "extract_text":
                    step["limit"] = _to_number(raw.get("limit"), 5, 1, 20, int)

            elif action == "scroll":
                direction = str(raw.get("direction", "down")).strip().lower()
                if direction not in ("down", "up"):
                    raise ValueError("direction must be 'down' or 'up'")
                step["direction"] = direction
                step["pixels"] = _to_number(raw.get("pixels"), 500, 1, 5000, int)

            elif action == "wait":
                step["seconds"] = _to_number(raw.get("seconds"), 2, 0, 10, float)
        except ValueError as e:
            raise ValueError(f"step {i} ({action}): {e}") from e

        clean.append(step)

    return clean


def describe_step(step):
    """One-line, human readable description of a step."""
    action = step.get("action")
    selector = step.get("selector", "")

    if action == "open":
        text = f"Open {step.get('url', '')}"
    elif action == "click":
        text = f"Click {selector}"
    elif action == "type":
        typed = step.get("text", "")
        typed = typed if len(typed) <= 40 else typed[:37] + "..."
        text = f'Type "{typed}" into {selector}'
    elif action == "press_enter":
        text = f"Press Enter in {selector}"
    elif action == "wait_for_element":
        text = f"Wait for {selector}"
    elif action == "scroll":
        text = f"Scroll {step.get('direction', 'down')} {step.get('pixels', 500)}px"
    elif action == "wait":
        text = f"Wait {step.get('seconds', 2):g}s"
    elif action == "extract_text":
        text = f"Read text from {selector}"
    else:
        text = f"Run {action}"

    return " ".join(text.split())  # single line, no stray whitespace


# ---------------------------------------------------------------------------
# Browser setup
# ---------------------------------------------------------------------------
def get_stealth_chrome_options():
    options = ChromeOptions()
    if HEADLESS:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1280,720")
    # "eager" returns once the DOM is ready, so slow ads/trackers can't hang a step.
    options.page_load_strategy = "eager"

    options.add_argument("--enable-unsafe-swiftshader")
    options.add_argument("--disable-software-rasterizer")

    if CHROME_BIN:
        options.binary_location = CHROME_BIN
    if CHROME_DEBUG_PORT:
        options.add_argument(f"--remote-debugging-port={CHROME_DEBUG_PORT}")

    user_agent = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
    options.add_argument(f"user-agent={user_agent}")

    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    return options


def apply_stealth(driver):
    """Applies browser fingerprint masking using selenium-stealth."""
    stealth(
        driver,
        languages=["en-US", "en"],
        vendor="Google Inc.",
        platform="Win32",
        webgl_vendor="Intel Inc.",
        renderer="Intel Iris OpenGL Engine",
        fix_hairline=True,
    )


# ---------------------------------------------------------------------------
# Step execution
# ---------------------------------------------------------------------------
def _scroll_into_view(driver, element):
    try:
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
    except WebDriverException:
        pass


def _safe_click(driver, element):
    """Clicks an element, falls back to a JS click, and follows links that open a new tab."""
    _scroll_into_view(driver, element)
    handles_before = set(driver.window_handles)
    time.sleep(0.3)

    try:
        element.click()
    except (ElementClickInterceptedException, ElementNotInteractableException):
        driver.execute_script("arguments[0].click();", element)

    time.sleep(1)

    new_tabs = [h for h in driver.window_handles if h not in handles_before]
    if new_tabs:
        driver.switch_to.window(new_tabs[-1])
        return {"detail": "Followed the link into a new tab"}
    return {}


def execute_step(driver, wait, step):
    """Runs a single validated step. Returns {"detail": str, "extracted": [str]} (both optional)."""
    action = step["action"]

    if action == "open":
        driver.get(step["url"])
        time.sleep(1.5)
        return {}

    if action == "wait":
        time.sleep(step["seconds"])
        return {}

    if action == "scroll":
        delta = step["pixels"] if step["direction"] == "down" else -step["pixels"]
        driver.execute_script("window.scrollBy(0, arguments[0]);", delta)
        time.sleep(0.3)
        return {}

    locator = (BY_MAP[step["selector_type"]], step["selector"])

    if action == "wait_for_element":
        wait.until(EC.presence_of_element_located(locator))
        return {}

    if action == "type":
        element = wait.until(EC.element_to_be_clickable(locator))
        _scroll_into_view(driver, element)
        try:
            element.clear()
        except WebDriverException:
            pass
        time.sleep(0.3)
        element.send_keys(step["text"])
        return {}

    if action == "click":
        element = wait.until(EC.element_to_be_clickable(locator))
        return _safe_click(driver, element)

    if action == "press_enter":
        element = wait.until(EC.presence_of_element_located(locator))
        element.send_keys(Keys.RETURN)
        time.sleep(1)
        return {}

    if action == "extract_text":
        elements = wait.until(EC.presence_of_all_elements_located(locator))
        texts = []
        for element in elements[: step["limit"]]:
            text = (element.text or element.get_attribute("textContent") or "").strip()
            if text:
                texts.append(text)
        return {"detail": f"Read {len(texts)} item(s)", "extracted": texts}

    raise ValueError(f"Unsupported action: {action}")


def friendly_error(exc, step):
    if isinstance(exc, TimeoutException):
        target = step.get("selector")
        if target:
            return (f"Timed out after {STEP_TIMEOUT}s. The element '{target}' was not found "
                    "or could not be clicked. Edit the selector in the plan and run it again.")
        return f"Timed out after {STEP_TIMEOUT}s"

    message = (getattr(exc, "msg", None) or str(exc) or "").strip()
    first_line = message.splitlines()[0] if message else ""
    return first_line or exc.__class__.__name__


def run_selenium_stream(steps):
    """
    Executes the steps and yields progress events:
    browser_starting, step_start, step_done, step_error, completed, error.
    """
    driver = None
    total = len(steps)

    try:
        yield {"status": "browser_starting", "message": "Starting the browser..."}
        driver = webdriver.Chrome(options=get_stealth_chrome_options())
        driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
        apply_stealth(driver)
        wait = WebDriverWait(driver, STEP_TIMEOUT)

        for idx, step in enumerate(steps, start=1):
            yield {
                "status": "step_start",
                "step_index": idx,
                "total_steps": total,
                "label": describe_step(step),
            }

            step_started = time.time()
            try:
                result = execute_step(driver, wait, step)
            except Exception as exc:
                error_text = friendly_error(exc, step)
                yield {
                    "status": "step_error",
                    "step_index": idx,
                    "total_steps": total,
                    "message": error_text,
                }
                yield {
                    "status": "error",
                    "message": f"Step {idx} of {total} failed: {error_text}",
                }
                return

            yield {
                "status": "step_done",
                "step_index": idx,
                "total_steps": total,
                "duration": round(time.time() - step_started, 1),
                "label": describe_step(step),
                "detail": result.get("detail"),
                "extracted": result.get("extracted"),
                "selector": step.get("selector"),
            }

        yield {
            "status": "completed",
            "message": "Automation completed successfully!",
            "total_steps": total,
        }

    except Exception as exc:
        yield {"status": "error", "message": f"Execution failed: {friendly_error(exc, {})}"}
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Standalone script generation
# ---------------------------------------------------------------------------
SCRIPT_HELPERS = '''def safe_click(element):
    """Click an element; fall back to a JS click and follow links that open a new tab."""
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
    handles_before = set(driver.window_handles)
    time.sleep(0.3)
    try:
        element.click()
    except (ElementClickInterceptedException, ElementNotInteractableException):
        driver.execute_script("arguments[0].click();", element)
    time.sleep(1)
    new_tabs = [h for h in driver.window_handles if h not in handles_before]
    if new_tabs:
        driver.switch_to.window(new_tabs[-1])
'''


def generate_python_code(steps):
    """Builds a standalone Selenium script for the plan. All values go through repr() so
    quotes or odd characters in URLs, selectors or text can't break the generated code."""
    lines = [
        "# pip install selenium selenium-stealth",
        "from selenium import webdriver",
        "from selenium.common.exceptions import (",
        "    ElementClickInterceptedException,",
        "    ElementNotInteractableException,",
        ")",
        "from selenium.webdriver.common.by import By",
        "from selenium.webdriver.common.keys import Keys",
        "from selenium.webdriver.chrome.options import Options",
        "from selenium.webdriver.support.ui import WebDriverWait",
        "from selenium.webdriver.support import expected_conditions as EC",
        "from selenium_stealth import stealth",
        "import time",
        "",
        "options = Options()",
        'options.add_argument("--disable-blink-features=AutomationControlled")',
        'options.add_experimental_option("excludeSwitches", ["enable-automation"])',
        'options.add_experimental_option("useAutomationExtension", False)',
        'options.add_argument("--start-maximized")',
        "",
        "driver = webdriver.Chrome(options=options)",
        "stealth(",
        "    driver,",
        '    languages=["en-US", "en"],',
        '    vendor="Google Inc.",',
        '    platform="Win32",',
        '    webgl_vendor="Intel Inc.",',
        '    renderer="Intel Iris OpenGL Engine",',
        "    fix_hairline=True,",
        ")",
        f"wait = WebDriverWait(driver, {STEP_TIMEOUT})",
        "",
        "",
        SCRIPT_HELPERS,
        "try:",
    ]

    for idx, step in enumerate(steps, start=1):
        action = step.get("action")
        by = "By." + BY_CODE.get(step.get("selector_type", "css"), "CSS_SELECTOR")
        locator = f"({by}, {step.get('selector', '')!r})"

        lines.append(f"    # Step {idx}: {describe_step(step)}")

        if action == "open":
            lines.append(f"    driver.get({step.get('url', '')!r})")
            lines.append("    time.sleep(1.5)")

        elif action == "wait_for_element":
            lines.append(f"    wait.until(EC.presence_of_element_located({locator}))")

        elif action == "type":
            lines.append(f"    elem = wait.until(EC.element_to_be_clickable({locator}))")
            lines.append("    elem.clear()")
            lines.append(f"    elem.send_keys({step.get('text', '')!r})")

        elif action == "click":
            lines.append(f"    safe_click(wait.until(EC.element_to_be_clickable({locator})))")

        elif action == "press_enter":
            lines.append(f"    wait.until(EC.presence_of_element_located({locator})).send_keys(Keys.RETURN)")
            lines.append("    time.sleep(1)")

        elif action == "scroll":
            pixels = int(step.get("pixels", 500))
            value = pixels if step.get("direction", "down") == "down" else -pixels
            lines.append(f'    driver.execute_script("window.scrollBy(0, {value});")')

        elif action == "wait":
            lines.append(f"    time.sleep({step.get('seconds', 2):g})")

        elif action == "extract_text":
            lines.append(f"    elements = wait.until(EC.presence_of_all_elements_located({locator}))")
            lines.append(f"    for element in elements[:{int(step.get('limit', 5))}]:")
            lines.append("        print(element.text.strip())")

        lines.append("")

    lines.extend([
        '    print("Automation sequence completed successfully!")',
        "except Exception as e:",
        '    print(f"Execution failed: {e}")',
        "finally:",
        "    time.sleep(2)",
        "    driver.quit()",
        "",
    ])

    return "\n".join(lines)

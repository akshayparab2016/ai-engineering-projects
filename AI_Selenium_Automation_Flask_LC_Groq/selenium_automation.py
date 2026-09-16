import os
import time
import base64
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium_stealth import stealth

def get_stealth_chrome_options():
    options = ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--remote-debugging-port=9222")
    options.add_argument("--window-size=1280,720")
    
    options.add_argument("--enable-unsafe-swiftshader") 
    options.add_argument("--disable-software-rasterizer")
    
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    options.add_argument(f"user-agent={user_agent}")
    
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
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

def take_screenshot(driver):
    """Captures base64 screenshot safely after confirming page readiness."""
    try:
        time.sleep(0.5)
        return driver.get_screenshot_as_base64()
    except Exception:
        return None

def run_selenium_stream(steps):
    """Executes automation steps with full action handling and screenshot streaming."""
    options = get_stealth_chrome_options()
    driver = None
    try:
        driver = webdriver.Chrome(options=options)
        apply_stealth(driver)
        
        wait = WebDriverWait(driver, 15)

        for idx, step in enumerate(steps):
            action = step.get("action")
            step_description = f"Step {idx + 1}/{len(steps)}: Executing {action}"

            # 1. Open URL
            if action == "open":
                url = step.get("url", "")
                if url:
                    driver.get(url)
                    time.sleep(1.5)

            # 2. Wait for Element
            elif action == "wait_for_element":
                by_type = getattr(By, str(step.get("selector_type", "css")).upper(), By.CSS_SELECTOR)
                selector = step.get("selector", "")
                if selector:
                    wait.until(EC.presence_of_element_located((by_type, selector)))

            # 3. Interactive Actions (type, click, press_enter)
            elif action in ["type", "click", "press_enter"]:
                by_type = getattr(By, str(step.get("selector_type", "css")).upper(), By.CSS_SELECTOR)
                selector = step.get("selector", "")
                if not selector:
                    continue

                if action == "type":
                    element = wait.until(EC.element_to_be_clickable((by_type, selector)))
                    element.clear()
                    time.sleep(0.4)
                    element.send_keys(step.get("text", ""))

                elif action == "click":
                    element = wait.until(EC.element_to_be_clickable((by_type, selector)))
                    time.sleep(0.4)
                    element.click()

                elif action == "press_enter":
                    element = wait.until(EC.presence_of_element_located((by_type, selector)))
                    element.send_keys(Keys.RETURN)

            # 4. Scroll Action
            elif action == "scroll":
                direction = step.get("direction", "down")
                pixels = step.get("pixels", 500)
                scroll_y = pixels if direction == "down" else -pixels
                driver.execute_script(f"window.scrollBy(0, {scroll_y});")

            # 5. Timed Pause
            elif action == "wait":
                time.sleep(step.get("seconds", 2))

            yield {
                "status": "in_progress",
                "message": f"Completed: {step_description}",
                "screenshot": take_screenshot(driver),
                "step_index": idx + 1,
                "total_steps": len(steps)
            }

        yield {
            "status": "completed",
            "message": "Automation completed successfully! Standalone Python code and AI JSON plan are generated below.",
            "screenshot": take_screenshot(driver)
        }

    except Exception as e:
        error_msg = str(e).split("\n")[0]
        yield {
            "status": "error",
            "message": f"Execution failed: {error_msg}",
            "screenshot": take_screenshot(driver) if driver else None
        }
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass


def generate_python_code(steps):
    code_lines = [
        "from selenium import webdriver",
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
        'options.add_argument("--start-maximized")',
        "",
        "driver = webdriver.Chrome(options=options)",
        "stealth(driver, languages=['en-US', 'en'], vendor='Google Inc.', platform='Win32', fix_hairline=True)",
        "wait = WebDriverWait(driver, 15)",
        "",
        "try:"
    ]

    for step in steps:
        action = step.get("action")
        by_type = str(step.get("selector_type", "css")).upper()
        selector = step.get("selector", "")

        if action == "open":
            url = step.get("url", "")
            code_lines.append(f'    driver.get("{url}")')
            code_lines.append("    time.sleep(1.5)")

        elif action == "wait_for_element":
            code_lines.append(f'    wait.until(EC.presence_of_element_located((By.{by_type}, "{selector}")))')

        elif action == "type":
            text = step.get("text", "")
            code_lines.append(f'    elem = wait.until(EC.element_to_be_clickable((By.{by_type}, "{selector}")))')
            code_lines.append("    elem.clear()")
            code_lines.append("    time.sleep(0.4)")
            code_lines.append(f'    elem.send_keys("{text}")')

        elif action == "click":
            code_lines.append(f'    elem = wait.until(EC.element_to_be_clickable((By.{by_type}, "{selector}")))')
            code_lines.append("    time.sleep(0.4)")
            code_lines.append("    elem.click()")

        elif action == "press_enter":
            code_lines.append(f'    elem = wait.until(EC.presence_of_element_located((By.{by_type}, "{selector}")))')
            code_lines.append("    elem.send_keys(Keys.RETURN)")

        elif action == "scroll":
            pixels = step.get("pixels", 500)
            direction = step.get("direction", "down")
            val = pixels if direction == "down" else -pixels
            code_lines.append(f'    driver.execute_script("window.scrollBy(0, {val});")')

        elif action == "wait":
            code_lines.append(f'    time.sleep({step.get("seconds", 2)})')

    code_lines.extend([
        "    print('Automation sequence completed successfully!')",
        "except Exception as e:",
        "    print(f'Execution Failed: {e}')",
        "finally:",
        "    time.sleep(2)",
        "    driver.quit()"
    ])

    return "\n".join(code_lines)
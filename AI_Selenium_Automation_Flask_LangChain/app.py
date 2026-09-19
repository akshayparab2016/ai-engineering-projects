import spaces
import os
import json
import threading

from flask import Flask, Response, jsonify, render_template, request

from ai_agent import stream_automation
from automation import (
    generate_python_code,
    run_selenium_stream,
    validate_steps,
)

app = Flask(__name__)

MAX_INSTRUCTION_LENGTH = 1000
MAX_CONCURRENT_RUNS = int(os.getenv("MAX_CONCURRENT_RUNS", "2"))

# Every run starts a real Chrome process, so only allow a few at the same time.
run_slots = threading.BoundedSemaphore(MAX_CONCURRENT_RUNS)


def sse(payload):
    """Formats a dict as one Server-Sent Event."""
    return f"data: {json.dumps(payload)}\n\n"


def sse_response(events):
    return Response(
        events,
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


def error_response(message):
    return sse_response(iter([sse({"status": "error", "message": message})]))


def plan_event(steps):
    """The event that sends the final plan and the generated Python code."""
    return sse({
        "status": "initialized",
        "ai_result": steps,
        "python_code": generate_python_code(steps),
        "total_steps": len(steps),
    })


def guarded_run(steps):
    """Streams a browser run while holding one of the limited run slots."""
    if not run_slots.acquire(blocking=False):
        yield sse({
            "status": "error",
            "message": "The server is running other automations right now. Try again in a moment.",
        })
        return

    try:
        for update in run_selenium_stream(steps):
            yield sse(update)
    finally:
        # Also runs when the browser tab is closed or the Stop button is pressed,
        # so the slot is always released and Chrome is shut down.
        run_slots.release()


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/automate-stream", methods=["POST"])
def automate_stream():
    """Instruction -> AI plan -> browser run (streamed)."""
    data = request.get_json(silent=True) or {}
    instruction = str(data.get("instruction", "")).strip()

    if not instruction:
        return error_response("Please enter a valid instruction.")
    if len(instruction) > MAX_INSTRUCTION_LENGTH:
        return error_response(f"Instructions are limited to {MAX_INSTRUCTION_LENGTH} characters.")

    def event_stream():
        try:
            yield sse({"status": "planning", "message": "Generating the action plan..."})

            steps = None
            for event in stream_automation(instruction, validator=validate_steps):
                if event["type"] == "chunk":
                    # Raw model output, shown live in the JSON pane while it is being written.
                    yield sse({"status": "plan_chunk", "text": event["text"]})
                elif event["type"] == "retry":
                    yield sse({
                        "status": "plan_retry",
                        "message": f"The plan was rejected ({event['message']}). Asking the AI to try again...",
                    })
                elif event["type"] == "plan":
                    steps = event["steps"]

            yield plan_event(steps)
            yield from guarded_run(steps)
        except Exception as e:
            yield sse({"status": "error", "message": str(e)})

    return sse_response(event_stream())


@app.route("/run-plan", methods=["POST"])
def run_plan():
    """Runs a plan directly (for example one edited in the UI) without calling the AI."""
    data = request.get_json(silent=True) or {}

    try:
        steps = validate_steps(data.get("steps"))
    except ValueError as e:
        return error_response(f"Invalid plan: {e}")

    def event_stream():
        try:
            yield plan_event(steps)
            yield from guarded_run(steps)
        except Exception as e:
            yield sse({"status": "error", "message": str(e)})

    return sse_response(event_stream())


@spaces.GPU
def main():
    port = int(os.environ.get("PORT", 7860))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()    

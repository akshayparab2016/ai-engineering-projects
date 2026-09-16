import os
import spaces
import json
from flask import Flask, render_template, request, Response
from ai_agent import generate_automation
from selenium_automation import run_selenium_stream, generate_python_code

app = Flask(__name__)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/automate-stream", methods=["POST"])
def automate_stream():
    data = request.get_json() or {}
    instruction = data.get("instruction", "").strip()

    if not instruction:
        def error_event():
            yield f"data: {json.dumps({'status': 'error', 'message': 'Please enter a valid instruction.'})}\n\n"
        return Response(
            error_event(), 
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive"
            }
        )

    def event_stream():
        try:
            # Step 1: Generate Action Plan
            ai_result = generate_automation(instruction)
            python_code = generate_python_code(ai_result)

            # Send initial metadata event
            yield f"data: {json.dumps({'status': 'initialized', 'ai_result': ai_result, 'python_code': python_code})}\n\n"

            # Step 2: Stream Selenium Execution & Screenshots
            for update in run_selenium_stream(ai_result):
                yield f"data: {json.dumps(update)}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'status': 'error', 'message': str(e)})}\n\n"

    return Response(
        event_stream(), 
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive"
        }
    )

    
if __name__ == "__main__":
    app.run(debug=True)
    
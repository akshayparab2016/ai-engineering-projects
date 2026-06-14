import json
from flask import Flask, render_template, request, Response
from graph import build_graph
import os

app = Flask(__name__)
debate_graph = build_graph()

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/stream")
def stream():
    topic = request.args.get("topic", "").strip()
    if not topic:
        return "data: Missing topic\n\n"

    def generate():
        try:
            # stream_mode="messages" streams individual LLM tokens as they generate
            for chunk in debate_graph.stream(
                {"topic": topic}, 
                stream_mode="messages",
                version="v2"
            ):
                # Under version="v2", the iterator yields a dictionary payload
                if isinstance(chunk, dict) and chunk.get("type") == "messages":
                    # data contains a 2-tuple: (MessageChunk, MetadataDict)
                    msg_data = chunk.get("data")
                    if not msg_data or len(msg_data) < 2:
                        continue
                        
                    token, metadata = msg_data
                    
                    # Read the text string content out of the message token
                    if token and hasattr(token, "content") and token.content:
                        node_name = metadata.get("langgraph_node")
                        
                        # Match the current active node step directly with the frontend CSS roles
                        role = None
                        if node_name == "pro":
                            role = "pro"
                        elif node_name == "opp":
                            role = "opp"
                        elif node_name == "judge":
                            role = "judge"
                        
                        if role:
                            payload = {"role": role, "text": token.content}
                            yield f"data: {json.dumps(payload)}\n\n"
                            
        except Exception as e:
            yield f"data: {json.dumps({'role': 'error', 'text': str(e)})}\n\n"
        
        yield "data: [DONE]\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disables nginx buffer delays
        }
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    app.run(host="0.0.0.0", port=port) 
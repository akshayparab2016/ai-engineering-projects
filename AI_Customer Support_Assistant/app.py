from flask import Flask, render_template, request, jsonify
from support_graph import support_app
import os

app = Flask(__name__)

# ==========================================
# HOME PAGE
# ==========================================

@app.route("/")
def home():
    return render_template("index.html")

# ==========================================
# CHAT API
# ==========================================

@app.route("/chat", methods=["POST"])
def chat():

    data = request.get_json()

    customer_name = data.get("name", "").strip()
    question = data.get("message", "").strip()

    if not customer_name:
        return jsonify(
            {
                "error": "Customer name is required"
            }
        ), 400

    if not question:
        return jsonify(
            {
                "error": "Message is required"
            }
        ), 400

    try:

        result = support_app.invoke(
            {
                "customer_name": customer_name,
                "question": question
            }
        )

        return jsonify(
            {
                "ticket_id": result.get("ticket_id"),

                "department": result.get(
                    "department",
                    "General"
                ),

                "priority": result.get(
                    "priority",
                    "Medium"
                ),

                "sentiment": result.get(
                    "sentiment",
                    "Neutral"
                ),

                "confidence": result.get(
                    "confidence",
                    "N/A"
                ),

                "summary": result.get(
                    "summary",
                    ""
                ),

                "response": result.get(
                    "answer",
                    "No response generated."
                ),

                "ticket_closed": result.get(
                    "ticket_closed",
                    False
                ),

                "escalation": result.get(
                    "escalation",
                    False
                ),

                # Agent outputs (useful for future dashboard)
                "tech_response": result.get(
                    "tech_response",
                    ""
                ),

                "billing_response": result.get(
                    "billing_response",
                    ""
                ),

                "sales_response": result.get(
                    "sales_response",
                    ""
                ),

                "reviewer_response": result.get(
                    "reviewer_response",
                    ""
                )
            }
        )

    except Exception as e:

        return jsonify(
            {
                "error": str(e)
            }
        ), 500

# ==========================================
# RUN
# ==========================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    app.run(host="0.0.0.0", port=port)
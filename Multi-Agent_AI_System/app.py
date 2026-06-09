from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

from agents.research_agent import research_agent
from agents.coding_agent import coding_agent
from agents.summary_agent import summary_agent
from agents.planner_agent import planner_agent

load_dotenv()

app = Flask(__name__)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/run_agent", methods=["POST"])
def run_agent():

    data = request.get_json()

    query = data.get("query", "").strip()

    if not query:
        return jsonify({
            "error": "Prompt cannot be empty."
        }), 400

    agent = data.get("agent")

    try:

        if agent == "research":
            result = research_agent(query)

        elif agent == "coding":
            result = coding_agent(query)

        elif agent == "summary":
            result = summary_agent(query)

        elif agent == "planner":
            result = planner_agent(query)

        else:
            return jsonify({
                "error": "Invalid agent selected."
            }), 400

        return jsonify({
            "result": result
        })

    except Exception as e:

        return jsonify({
            "error": str(e)
        }), 500


if __name__ == "__main__":
    app.run(debug=True)
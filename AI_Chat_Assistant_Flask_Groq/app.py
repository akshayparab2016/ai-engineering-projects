from groq import Groq
from flask import Flask, render_template, request
from dotenv import load_dotenv
import os

load_dotenv()
app = Flask(__name__)

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

@app.route("/", methods=["GET", "POST"])
def home():
    ai_response = ""
    if request.method == "POST":
        prompt = request.form.get("prompt", "")

        try:
            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            ai_response = completion.choices[0].message.content

        except Exception as e:
            ai_response = f"Error: {str(e)}"

    return render_template(
        "index.html",
        ai_response=ai_response
    )

if __name__ == "__main__":
    app.run(debug=True)
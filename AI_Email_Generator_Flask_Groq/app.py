from flask import Flask, render_template, request
from groq import Groq
from dotenv import load_dotenv
import os

load_dotenv()
app = Flask(__name__)

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

@app.route("/", methods=["GET", "POST"])
def home():
    email_content = ""
    if request.method == "POST":
        purpose = request.form.get("purpose")
        tone = request.form.get("tone")
        prompt = f"""
        Write a professional email based on the given topic.

        Purpose:
        {purpose}

        Tone:
        {tone}

        Generate:
        Subject Line

        Email Body

        Signature
        """

        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=800
            )
            email_content = response.choices[0].message.content
        except Exception as e:
            email_content = f"Error: {str(e)}"

    return render_template("index.html", email_content=email_content)

if __name__ == "__main__":
    app.run(debug=True)
from flask import Flask, render_template, request
from groq import Groq
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)

client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)

def generate_content(prompt):
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.7,
        max_tokens=2000
    )

    return response.choices[0].message.content


@app.route("/", methods=["GET", "POST"])
def home():

    result = ""
    if request.method == "POST":
        content_type = request.form.get("content_type")
        topic = request.form.get("topic")

        if content_type == "blog":
            prompt = f"""
            Write a professional blog article about:
            {topic}

            Include:
            - Title
            - Introduction
            - Headings
            - Conclusion
            """

        elif content_type == "social":
            prompt = f"""
            Create engaging social media posts about:
            {topic}

            Include:
            - Instagram Post
            - LinkedIn Post
            - Twitter/X Post
            - Relevant hashtags
            """

        elif content_type == "product":
            prompt = f"""
            Create a persuasive product description for:
            {topic}

            Include:
            - Product Title
            - Features
            - Benefits
            - Call to Action
            """
        result = generate_content(prompt)
    return render_template("index.html", result=result)


if __name__ == "__main__":
    app.run(debug=True)
import os
import shutil

from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
import uuid
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_classic.chains.retrieval import create_retrieval_chain
from langchain_classic.chains.combine_documents import (
    create_stuff_documents_chain
)

load_dotenv()

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
CHROMA_DIR = "chroma_db"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

embedding_model = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

llm = ChatGroq(
    groq_api_key=os.getenv("GROQ_API_KEY"),
    model_name="llama-3.3-70b-versatile",
    temperature=0
)

vectorstore = None
qa_chain = None




@app.route("/")
def home():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload_pdf():

    global vectorstore
    global qa_chain

    try:

        files = request.files.getlist("files")

        if not files:
            return jsonify({
                "error": "No files uploaded"
            })

        pdf_paths = []

        for file in files:

            if file.filename == "":
                continue

            if not file.filename.lower().endswith(".pdf"):
                return jsonify({
                    "error": f"{file.filename} is not a PDF"
                })

            filename = secure_filename(file.filename)

            filepath = os.path.join(
                UPLOAD_FOLDER,
                filename
            )

            file.save(filepath)

            pdf_paths.append(filepath)

        vectorstore, qa_chain = process_pdfs(
            pdf_paths
        )

        return jsonify({
            "message": f"{len(pdf_paths)} PDFs uploaded successfully"
        })

    except Exception as e:

        return jsonify({
            "error": str(e)
        })        

def process_pdfs(pdf_paths):

    all_documents = []

    for pdf_path in pdf_paths:

        loader = PyPDFLoader(pdf_path)

        documents = loader.load()

        for doc in documents:
            doc.metadata["source_file"] = os.path.basename(pdf_path)

        all_documents.extend(documents)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=200
    )

    chunks = splitter.split_documents(
        all_documents
    )

    db_path = os.path.join(
        CHROMA_DIR,
        str(uuid.uuid4())
    )

    db = Chroma.from_documents(
        documents=chunks,
        embedding=embedding_model,
        persist_directory=db_path
    )

    retriever = db.as_retriever(
        search_type="similarity",
        search_kwargs={"k": 6}
    )

    prompt = ChatPromptTemplate.from_template(
        """You are an AI assistant that answers questions about uploaded PDF documents.
        Rules:
        1. Answer questions ONLY using the information provided in the context.
        2. Do NOT use your own knowledge or make assumptions.
        3. If the answer is not explicitly present in the context, respond with: "I could not find that information in the uploaded PDFs."
        4. If the user sends a greeting such as: Hi, Hello, Hey, Good Morning, Good Afternoon, Good Evening, then respond with a friendly greeting and invite them to ask questions about the uploaded PDFs.
        Example: "Hello! 👋 How can I help you with your uploaded PDFs today?"
        5. For simple conversational messages such as: Thanks, Thank you, Bye, Goodbye, respond politely and naturally.
        6. Keep answers concise, accurate, and based only on the provided context.

        Context:
        {context}

        Question:
        {input}"""
    )

    document_chain = create_stuff_documents_chain(
        llm,
        prompt
    )

    retrieval_chain = create_retrieval_chain(
        retriever,
        document_chain
    )

    return db, retrieval_chain

@app.route("/ask", methods=["POST"])
def ask_question():

    global qa_chain

    if qa_chain is None:
        return jsonify({
            "answer": "Upload a PDF first."
        })

    data = request.get_json()

    question = data.get(
        "question",
        ""
    ).strip()

    if not question:
        return jsonify({
            "answer": "Please enter a question."
        })

    try:

        result = qa_chain.invoke({
            "input": question
        })

        return jsonify({
            "answer": result["answer"]
        })

    except Exception as e:

        return jsonify({
            "answer": f"Error: {str(e)}"
        })


if __name__ == "__main__":
    app.run()
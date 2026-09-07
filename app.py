import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from google import genai
from google.genai import types

from chatbot_config import SYSTEM_PROMPT

load_dotenv()

app = Flask(__name__)

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = "gemini-3.1-flash-lite"
KNOWLEDGE_FILE = Path(os.getenv("KNOWLEDGE_FILE", "knowledge.txt"))

if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not configured in the .env file.")

client = genai.Client(api_key=API_KEY)


def load_knowledge():
    if not KNOWLEDGE_FILE.exists():
        return ""
    return KNOWLEDGE_FILE.read_text(encoding="utf-8")


def retrieve_context(query, knowledge):
    """Simple local retrieval layer using keyword overlap."""
    if not knowledge.strip():
        return ""

    query_terms = {
        word.lower()
        for word in query.split()
        if len(word.strip(".,!?;:()[]{}\"'")) > 2
    }

    chunks = [
        chunk.strip()
        for chunk in knowledge.split("\n\n")
        if chunk.strip()
    ]

    scored = []
    for chunk in chunks:
        chunk_terms = set(chunk.lower().split())
        score = sum(1 for term in query_terms if term in chunk_terms)
        if score:
            scored.append((score, chunk))

    scored.sort(key=lambda item: item[0], reverse=True)

    return "\n\n".join(chunk for _, chunk in scored[:5])


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/chat")
def chat():
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()

    if not message:
        return jsonify({"error": "Please enter a question."}), 400

    knowledge = load_knowledge()
    context = retrieve_context(message, knowledge)

    prompt = f"""
{SYSTEM_PROMPT}

RETRIEVED KNOWLEDGE:
{context if context else "No relevant information was retrieved."}

USER QUESTION:
{message}

Answer using only the retrieved knowledge. If the retrieved knowledge does not
contain enough information to answer, clearly say that the information is not
available in the provided study material. Do not invent facts.
"""

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=600,
            ),
        )

        answer = (response.text or "").strip()
        return jsonify({"answer": answer})

    except Exception as exc:
        app.logger.exception("Gemini request failed")
        return jsonify({"error": "Unable to generate a response right now."}), 500


if __name__ == "__main__":
    app.run(debug=True)

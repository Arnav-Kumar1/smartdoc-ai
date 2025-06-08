import os
import logging
import joblib
import numpy as np
from typing import Tuple, List, Dict, Any
from sklearn.metrics.pairwise import cosine_similarity
from app.config import VECTOR_STORE_DIR, TOP_K_CHUNKS
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

logger = logging.getLogger(__name__)

# Prompt template
QA_PROMPT = PromptTemplate.from_template("""
You are a helpful AI assistant. Answer the user's question using ONLY the following context from a document.

<context>
{context}
</context>

Question: {question}

Rules:
- If the answer is not found in the context, say "The answer is not found in the document."
- Be precise and concise.
""")

def get_llm() -> Any:
    """Returns the Gemini model instance."""
    return ChatGoogleGenerativeAI(model="gemini-1.5-flash-latest", temperature=0.3)

def build_qa_chain(llm, context: str) -> RetrievalQA:
    """Builds a RetrievalQA chain with injected context."""
    from langchain.chains import LLMChain
    from langchain_core.prompts import PromptTemplate as CorePromptTemplate
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.runnables import RunnableLambda
    prompt = CorePromptTemplate.from_template(QA_PROMPT.template)
    return LLMChain(prompt=prompt, llm=llm)

def load_vector_store(vector_store_path: str) -> Dict[str, Any]:
    """Loads TF-IDF vectorizer, matrix, and chunk list from disk."""
    try:
        vectorizer = joblib.load(os.path.join(vector_store_path, "vectorizer.pkl"))
        matrix = joblib.load(os.path.join(vector_store_path, "matrix.pkl"))
        chunks = joblib.load(os.path.join(vector_store_path, "chunks.pkl"))
        return {
            "vectorizer": vectorizer,
            "matrix": matrix,
            "chunks": chunks
        }
    except Exception as e:
        logger.error(f"Failed to load vector store from {vector_store_path}: {str(e)}")
        raise FileNotFoundError("Vector store files not found or corrupted.")

def retrieve_top_k_chunks(vector_store: Dict[str, Any], question: str, k: int = TOP_K_CHUNKS) -> List[str]:
    """Uses TF-IDF + cosine similarity to retrieve top-k most relevant chunks."""
    vectorizer = vector_store["vectorizer"]
    matrix = vector_store["matrix"]
    chunks = vector_store["chunks"]

    query_vector = vectorizer.transform([question])
    similarities = cosine_similarity(query_vector, matrix).flatten()
    top_indices = np.argsort(similarities)[::-1][:k]
    top_chunks = [chunks[i] for i in top_indices]
    return top_chunks

def run_qa_chain(llm: Any, question: str, context_chunks: List[str]) -> Tuple[str, List[Dict[str, str]]]:
    try:
        context = "\n\n".join(context_chunks)
        qa_chain = build_qa_chain(llm, context)
        response = qa_chain.invoke({"question": question, "context": context})

        answer = response.get("text", "").strip() or response.get("result", "").strip()
        if not answer:
            raise ValueError("Empty response from LLM")

        sources = [
            {"chunk_id": idx, "page_content": chunk[:200] + "..."}
            for idx, chunk in enumerate(context_chunks)
        ]
        return answer, sources

    except Exception as e:
        logger.error(f"QA chain failed: {str(e)}")
        raise RuntimeError(f"QA processing error: {str(e)}")

def rewrite_queries(llm, original_question: str, num_rephrasals: int = 4) -> list[str]:
    prompt = f"""
    Rephrase the following question to optimize for document retrieval.

    Rules:
    - Keep the original meaning but add more context to the question such that the answer can be found in the document.
    - Do not invent or include placeholders like [Source Document], [Topic], [Person], or [Event].
    - Use only terms that could plausibly appear in a real document or the original question.
    - Use clear and unambiguous wording.
    - Return exactly {num_rephrasals} different rephrased questions.
    - Do not include explanations or extra text.
    - Format the output as a numbered list, one question per line.

    Original Question: "{original_question}"
    """

    try:
        response = llm.invoke(prompt)
        text = response.content.strip() if hasattr(response, "content") else response
        rephrased_questions = []

        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            question = line.lstrip("0123456789. )").strip()
            if question:
                rephrased_questions.append(question)

        combined = [original_question] + [q for q in rephrased_questions if q.lower() != original_question.lower()]
        return combined[:num_rephrasals + 1]

    except Exception:
        return [original_question]

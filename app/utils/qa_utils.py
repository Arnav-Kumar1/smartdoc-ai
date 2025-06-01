import os
from typing import Tuple, List, Dict, Any

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

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

def load_vector_store(vector_store_path: str):
    """Loads the FAISS vector store from disk."""
    if not os.path.exists(vector_store_path):
        raise FileNotFoundError("Vector store not found. Please vectorize the document first.")

    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    vector_store = FAISS.load_local(vector_store_path, embeddings, allow_dangerous_deserialization=True)
    return vector_store

def setup_retriever(vector_store) -> Any:
    """Returns a configured retriever with MMR."""
    return vector_store.as_retriever(search_type="mmr", search_kwargs={"k": 10})

def get_llm() -> Any:
    """Returns the LLM instance (Gemini for now)."""
    return ChatGoogleGenerativeAI(model="gemini-1.5-flash-latest", temperature=0.3)

def build_qa_chain(llm, retriever) -> RetrievalQA:
    """Constructs a RetrievalQA chain with custom prompt."""
    return RetrievalQA.from_chain_type(
        llm=llm,
        retriever=retriever,
        chain_type="stuff",
        chain_type_kwargs={"prompt": QA_PROMPT},
        return_source_documents=True
    )

def run_qa_chain(chain: RetrievalQA, question: str) -> Tuple[str, List[Dict[str, str]]]:
    result = chain({"query": question})
    answer = result["result"]
    source_docs = result.get("source_documents", [])

    sources = []
    for doc in source_docs:
        sources.append({
            "chunk_id": doc.metadata.get("chunk_id", -1),  # fallback to -1 if not present
            "content": doc.page_content[:300]
        })

    return answer, sources




def rewrite_queries(llm, original_question: str, num_rephrasals: int = 4) -> list[str]:
    """
    Generate multiple rephrased versions of the original question for better semantic retrieval.

    Returns a list containing the original question plus num_rephrasals rephrased variants.
    """
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

        # Parse the numbered list from response
        rephrased_questions = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            # Remove leading numbers and dots, e.g. "1. " or "2) "
            question = line.lstrip("0123456789. )").strip()
            if question:
                rephrased_questions.append(question)

        # Return original + rephrasals, ensuring no duplicates
        combined = [original_question] + [q for q in rephrased_questions if q.lower() != original_question.lower()]
        return combined[:num_rephrasals + 1]  # max length = original + n rephrasals

    except Exception:
        return [original_question]

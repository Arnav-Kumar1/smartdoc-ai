import os
from typing import Tuple, List, Dict, Any

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from app import config
from app.config import EMBEDDING_MODEL_NAME, EMBEDDING_DIM
import logging
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



# Replace hardcoded model name with config reference
embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)

# Update vector store loading with dimension check
def load_vector_store(file_hash: str):
    vector_path = os.path.join(config.VECTOR_STORE_DIR, file_hash)
    
    if not os.path.exists(vector_path):
        os.makedirs(vector_path)
        return FAISS.from_texts([""], embeddings)
        
    try:
        vector_store = FAISS.load_local(vector_path, embeddings)
        if vector_store.index.d != EMBEDDING_DIM:  # Use config dimension
            raise ValueError(f"Dimension mismatch: Expected {EMBEDDING_DIM}, got {vector_store.index.d}")
        return vector_store
    except Exception as e:
        logger.error(f"Vector store load failed: {str(e)}")
        return FAISS.from_texts([""], embeddings, allow_dangerous_deserialization=True)


def load_vector_store(vector_store_path):  # Add parameter
    vector_store_dir = vector_store_path  # Use passed parameter instead of config
    embeddings = HuggingFaceEmbeddings(model_name=config.EMBEDDING_MODEL_NAME)
    
    if os.path.exists(vector_store_dir):
        return FAISS.load_local(
            folder_path=vector_store_dir,
            embeddings=embeddings,
            allow_dangerous_deserialization=True
        )
    return FAISS.from_texts([""], embeddings)


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
    try:
        result = chain({"query": question})
        
        if "result" not in result:
            raise ValueError("Missing 'result' in QA chain response")
            
        answer = result["result"]
        source_docs = result.get("source_documents", [])
        
        sources = []
        for doc in source_docs:
            sources.append({
                "chunk_id": doc.metadata.get("chunk_id", -1),
                "page_content": doc.page_content[:200] + "..."
            })
        return answer, sources
    except Exception as e:
        logger.error(f"QA chain failed: {str(e)}")
        raise RuntimeError(f"QA processing error: {str(e)}")




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

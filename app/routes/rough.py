from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_google_genai import ChatGoogleGenerativeAI

from langchain.chains import RetrievalQA

# Define request schema
class QAModel(BaseModel):
    filename: str
    question: str

router = APIRouter()

@router.post("/qa")
async def qa_query(payload: QAModel):
    vector_store_path = os.path.join("vector_store", payload.filename)

    if not os.path.exists(vector_store_path):
        raise HTTPException(status_code=404, detail="Vector store not found. Please vectorize the document first.")

    try:
        embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        vector_store = FAISS.load_local(vector_store_path, embeddings, allow_dangerous_deserialization=True)


        retriever = vector_store.as_retriever(search_type="mmr",search_kwargs={"k": 15})

        llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash-latest", temperature=0.3)

        qa_chain = RetrievalQA.from_chain_type(
            llm=llm,
            retriever=retriever,
            return_source_documents=False
        )

        custom_prompt = f"""
        You are an intelligent assistant helping the user understand the content of a document.
        Use only the information retrieved from the document.
        If the answer cannot be found in the provided context, clearly say so — do not guess.

        Question: {payload.question}
        """
        result = qa_chain.run(custom_prompt)

        return {"answer": result}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Q&A failed: {str(e)}")

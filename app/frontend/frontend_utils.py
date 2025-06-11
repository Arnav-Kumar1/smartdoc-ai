import requests
from typing import List
import io
from streamlit import cache_data
# from auth_wrapper import authenticated_request # This is not needed here anymore, as it's for backend internal
import requests # Ensure requests is imported
import time
from typing import Dict, List, Optional
import streamlit as st

# API endpoint
# API_URL = "https://smartdoc-ai-production.up.railway.app"
API_URL = "http://localhost:8000" # use this for locally testing
DEBUG = False  # Set to True during development


@cache_data(ttl=300)
def export_summary_as_txt(summary: str, filename: str) -> str:
    """Export summary as TXT"""
    txt_bytes = io.BytesIO()
    txt_bytes.write(f"Summary of {filename}\n\n".encode("utf-8"))
    txt_bytes.write(summary.encode("utf-8"))
    txt_bytes.seek(0)
    return f"Summary for {filename}:\n\n{summary}"


def login(email: str, password: str) -> bool:
    """Authenticate user and store token in session state"""
    try:
        # Normalize email to lowercase
        normalized_email = email.lower() if email else ""
        
        response = requests.post(
            f"{API_URL}/auth/token",
            data={"username": normalized_email, "password": password},
        )
        
        # Add debug information
        if DEBUG:
            print(f"Login response status: {response.status_code}")
            print(f"Login response content: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            st.session_state.token = data["access_token"]
            # Add debug print
            if DEBUG:
                print(f"Token set after login: {st.session_state.token[:10]}...")
            st.session_state.user_id = data["user_id"]
            st.session_state.username = data["username"]
            st.session_state.authenticated = True
            return True
        elif response.status_code == 401:
            error_detail = response.json().get("detail", "").lower()
            if "user not found" in error_detail or "incorrect email" in error_detail:
                st.error("Account not found. Please sign up first.")
            else:
                st.error("Invalid email or password")
            return False
        else:
            st.error(f"Login failed: {response.json().get('detail', 'Unknown error')}")
            return False
    except Exception as e:
        st.error(f"Login error: {str(e)}")
        return False


# MODIFIED: signup function now accepts gemini_api_key
def signup(email: str, username: str, password: str, gemini_api_key: str) -> bool:
    """Register a new user"""
    try:
        # Normalize email to lowercase
        normalized_email = email.lower() if email else ""
        
        # Add debug prints
        print(f"Attempting signup with email: {normalized_email}, username: {username}")
        
        # CHANGED: Use the /auth/signup endpoint and pass gemini_api_key
        response = requests.post(
            f"{API_URL}/auth/signup",
            json={
                "email": normalized_email,
                "username": username,
                "password": password,
                "gemini_api_key": gemini_api_key # NEW: Pass the Gemini API key
            },
        )
        
        # Add debug prints
        if DEBUG:
            print(f"Signup response status: {response.status_code}")
            print(f"Signup response content: {response.text}")
        
        # Handle specific response codes
        if response.status_code == 200: # FastAPI typically returns 200 for successful POST
            st.success("Account created successfully! Please log in.")
            return True
        elif response.status_code == 400:
            error_detail = response.json().get('detail', 'Unknown error')
            if "email already registered" in error_detail.lower():
                st.error("❗ Email already registered. Please use a different email or log in.")
            elif "invalid gemini api key" in error_detail.lower(): # NEW: Handle invalid API key
                st.error("⚠️ The provided Gemini API Key is invalid. Please check your key.")
            else:
                st.error(f"Signup failed: {error_detail}")
            return False
        else:
            try:
                error_detail = response.json().get('detail', 'Unknown error')
            except:
                error_detail = response.text or "Server error occurred"
            st.error(f"Signup failed: {error_detail}")
            return False
            
    except requests.exceptions.ConnectionError:
        st.error("🚫 Could not connect to the backend API. Please ensure the backend is running.")
        return False
    except Exception as e:
        print(f"Full signup error: {str(e)}")
        st.error(f"Signup error: {str(e)}")
        return False


def logout():
    """Clear authentication data from session state"""
    st.session_state.authenticated = False
    st.session_state.user_id = None
    st.session_state.username = None
    st.session_state.token = None
    st.session_state.current_page = "login"

# Helper function to make authenticated requests
def authenticated_request(method, endpoint, **kwargs):
    """Make an authenticated request to the API"""
    if not st.session_state.token:
        st.error("Authentication required")
        st.session_state.current_page = "login"
        return None

    headers = {"Authorization": f"Bearer {st.session_state.token}"}
    if "headers" in kwargs:
        kwargs["headers"].update(headers)
    else:
        kwargs["headers"] = headers

    try:
        response = method(f"{API_URL}{endpoint}", **kwargs)
        print(f"API request to {endpoint}: status={response.status_code}")
        if response.status_code == 401:
            st.error("Session expired. Please log in again.")
            logout()
            return None
        return response
    except Exception as e:
        print(f"Error in API request to {endpoint}: {str(e)}")
        st.error(f"API request failed: {str(e)}")
        return None


# Existing functions modified to use authenticated requests
def get_documents() -> List[Dict]:
    """Get cached documents or fetch fresh data"""
    cache_validity = 30  # seconds
    
    if (st.session_state.force_refresh 
        or st.session_state.documents_cache is None 
        or (time.time() - st.session_state.last_refresh) > cache_validity
    ):
        response = authenticated_request(requests.get, "/documents")
        if response and response.status_code == 200:
            st.session_state.documents_cache = response.json()
        else:
            st.session_state.documents_cache = []
        st.session_state.last_refresh = time.time()
        st.session_state.force_refresh = False
    
    return st.session_state.documents_cache


def upload_document(file) -> Optional[Dict]:
    """Upload a document with authentication"""
    try:
        files = {"file": (file.name, file, file.type)}
        response = authenticated_request(requests.post, "/upload", files=files)
        
        print(f"Upload response status: {response.status_code if response else 'No response'}")
        print(f"Upload response headers: {response.headers if response else 'No response'}")
        print(f"Upload response content: {response.text if response else 'No response'}")
        
        if response and response.status_code in (200, 201):
            try:
                print(f"Upload response JSON: {response.json()}")
            except Exception as e:
                print(f"Error parsing JSON: {e}")
            return response.json()
        elif response:
            print(f"Upload failed with status code: {response.status_code}")
            print(f"Response content: {response.text}")
            try:
                error_json = response.json()
                if isinstance(error_json, dict):
                    if "duplicate" in response.text.lower() or "already exists" in response.text.lower():
                        return {
                            "detail": f"File '{file.name}' can't be uploaded as it's a duplicate of an existing document"
                        }
                    if error_json.get("message") == "Duplicate document" or "duplicate" in str(error_json).lower():
                        return {
                            "detail": f"File '{error_json.get('attempted_filename', file.name)}' can't be uploaded as it's a duplicate of '{error_json.get('existing_filename', 'an existing document')}'"
                        }
                    return {"detail": error_json.get("detail", str(error_json))}
                return {"detail": str(error_json)}
            except Exception as e:
                print(f"JSON decode error: {e}")
                if response.text:
                    return {"detail": response.text}
                else:
                    return {"detail": "Unknown error"}
        return {"detail": f"File '{file.name}' can't be uploaded as it's a duplicate of an existing document"}
    except Exception as e:
        print(f"Exception during upload: {str(e)}")
        return {"detail": str(e)}


def summarize_document(document_id: str) -> Optional[Dict]:
    """Summarize a document with authentication"""
    documents = get_documents()
    document = next((doc for doc in documents if doc['id'] == document_id), None)
    
    if not document:
        print(f"Document with ID {document_id} not found")
        return None
    
    print(f"Attempting to summarize document: {document['filename']}")
    
    response = authenticated_request(requests.post, f"/summarize/{document['filename']}")
    if response and response.status_code == 200:
        print(f"Document summarized successfully: {document['filename']}")
        return response.json()
    elif response:
        print(f"Summarize failed with status code: {response.status_code}")
        print(f"Response content: {response.text}")
        
        if response.status_code == 403:
            return {
                "summary": "Error: You don't have permission to summarize this document.",
                "error": True
            }
        elif response.status_code == 404:
            return {
                "summary": "Error: Document not found. It may have been deleted.",
                "error": True
            }
        elif response.status_code == 400 and "gemini api key not found" in response.text.lower():
            return {
                "summary": "Error: Your Gemini API key is missing or invalid. Please ensure it is provided during signup.",
                "error": True
            }
        else:
            return {
                "summary": f"Error: Failed to summarize document (Status: {response.status_code})",
                "error": True
            }
    return None


def vectorize_document(document_id: str) -> Optional[Dict]:
    """Vectorize a document with authentication"""
    documents = get_documents()
    document = next((doc for doc in documents if doc['id'] == document_id), None)
    
    if not document:
        print(f"Document with ID {document_id} not found")
        return None
    
    print(f"Attempting to vectorize document: {document['filename']}")
    print(f"Document path: {document.get('path', 'Path not available')}")
    
    response = authenticated_request(requests.post, f"/vectorize/{document['filename']}")
    if response and response.status_code == 200:
        print(f"Document vectorized successfully: {document['filename']}")
        return response.json()
    elif response:
        print(f"Vectorize failed with status code: {response.status_code}")
        print(f"Response content: {response.text}")
    return None


def ask_question(document_id: str, question: str) -> Optional[Dict]:
    print(f"Making request to ask endpoint for document ID: {document_id}")
    print(f"Question: {question}")
    
    documents = get_documents()
    document = next((doc for doc in documents if doc['id'] == document_id), None)
    
    if not document:
        print(f"Document with ID {document_id} not found")
        return None
    
    print(f"Found document: {document}")
    
    data = {
        "filename": document['filename'],
        "question": question
    }
    
    print(f"Full request URL: {API_URL}/ask")
    print(f"Request headers: Authorization: Bearer {st.session_state.token[:10]}...")
    print(f"Request data: {data}")
    
    response = authenticated_request(
        requests.post, 
        "/ask", 
        json=data,
        headers={"Content-Type": "application/json"}
    )
    
    if response:
        print(f"Response status: {response.status_code}")
        print(f"Response content: {response.text}")
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            print("Document not found in database. Check if filename matches exactly.")
        elif response.status_code == 400 and "gemini api key not found" in response.text.lower():
            st.error("⚠️ Your Gemini API key is missing or invalid. Please ensure it is provided during signup.")
        else:
            st.error(f"❌ Failed to get answer: {response.json().get('detail', 'Unknown error')}")
    return None


def delete_document(document_id: str) -> bool:
    """Delete a document with authentication"""
    documents = get_documents()
    document = next((doc for doc in documents if doc['id'] == document_id), None)
    
    if not document:
        print(f"Document with ID {document_id} not found")
        return False
    
    response = authenticated_request(
        requests.delete, 
        f"/documents/{document['filename']}?document_id={document_id}"
    )
    
    if response and response.status_code == 200:
        print(f"Document and folder deleted successfully: {document['filename']}")
        return True
    else:
        print(f"Failed to delete document: {response.text if response else 'No response'}")
        return False

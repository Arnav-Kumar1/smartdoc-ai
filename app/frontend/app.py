import streamlit as st
import requests
import json
import os
import time
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone
import pytz


from frontend_utils import export_summary_as_txt

DEBUG = False  # Set to True during development
from contextlib import contextmanager

@contextmanager
def error_boundary():
    try:
        yield
    except Exception as e:
        st.error(f"Operation failed: {str(e)}")
        st.stop()

# API endpoint

API_URL = os.getenv("API_URL", "https://smartdoc-ai-production.up.railway.app")

# Session state initialization
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "username" not in st.session_state:
    st.session_state.username = None
if "token" not in st.session_state:
    st.session_state.token = None
if "current_page" not in st.session_state:
    st.session_state.current_page = "login"  # Default to login page
if "documents_cache" not in st.session_state:
    st.session_state.documents_cache = None
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = 0
if "force_refresh" not in st.session_state:
    st.session_state.force_refresh = False


# Authentication functions
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

def signup(email: str, username: str, password: str) -> bool:
    """Register a new user"""
    try:
        # Normalize email to lowercase
        normalized_email = email.lower() if email else ""
        
        # Add debug prints
        print(f"Attempting signup with email: {normalized_email}, username: {username}")
        
        response = requests.post(
            f"{API_URL}/auth/signup",
            json={"email": normalized_email, "username": username, "password": password},
        )
        
        # Add debug prints
        if DEBUG:
            print(f"Signup response status: {response.status_code}")
            print(f"Signup response content: {response.text}")
        
        # If response status is 500 but we know user was created
        if response.status_code == 500:
            # Check if user exists by trying to login
            login_response = requests.post(
                f"{API_URL}/auth/token",
                data={"username": normalized_email, "password": password},
            )
            if login_response.status_code == 200:
                st.success("Account created successfully! Please log in.")
                return True
        
        # Handle other response codes
        elif response.status_code in [200, 201]:
            st.success("Account created successfully! Please log in.")
            return True
        else:
            try:
                error_detail = response.json().get('detail', 'Unknown error')
            except:
                error_detail = response.text or "Server error occurred"
            st.error(f"Signup failed: {error_detail}")
            return False
            
    except Exception as e:
        print(f"Full signup error: {str(e)}")  # Debug print
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
        # Always return the response, even for 400 errors
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
        
        # Debug: print the actual response
        print(f"Upload response status: {response.status_code if response else 'No response'}")
        print(f"Upload response headers: {response.headers if response else 'No response'}")
        print(f"Upload response content: {response.text if response else 'No response'}")
        
        if response and response.status_code in (200, 201):
            # Debug: print the JSON response
            try:
                print(f"Upload response JSON: {response.json()}")
            except Exception as e:
                print(f"Error parsing JSON: {e}")
            return response.json()
        elif response:
            print(f"Upload failed with status code: {response.status_code}")
            print(f"Response content: {response.text}")
            # Try to extract 'detail' from JSON error response
            try:
                error_json = response.json()
                if isinstance(error_json, dict):
                    # Handle duplicate document case
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
    # First get the document details to get the filename
    documents = get_documents()
    document = next((doc for doc in documents if doc['id'] == document_id), None)
    
    if not document:
        print(f"Document with ID {document_id} not found")
        return None
    
    # Now summarize using the filename instead of ID
    print(f"Attempting to summarize document: {document['filename']}")
    
    response = authenticated_request(requests.post, f"/summarize/{document['filename']}")
    if response and response.status_code == 200:
        print(f"Document summarized successfully: {document['filename']}")
        return response.json()
    elif response:
        print(f"Summarize failed with status code: {response.status_code}")
        print(f"Response content: {response.text}")
        
        # Handle specific error cases
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
        else:
            return {
                "summary": f"Error: Failed to summarize document (Status: {response.status_code})",
                "error": True
            }
    return None

def vectorize_document(document_id: str) -> Optional[Dict]:
    """Vectorize a document with authentication"""
    # First get the document details to get the filename
    documents = get_documents()
    document = next((doc for doc in documents if doc['id'] == document_id), None)
    
    if not document:
        print(f"Document with ID {document_id} not found")
        return None
    
    # Now vectorize using the filename
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
    
    print(f"Found document: {document}")  # Add this line
    
    data = {
        "filename": document['filename'],
        "question": question
    }
    
    # Print full request details
    print(f"Full request URL: {API_URL}/ask")
    print(f"Request headers: Authorization: Bearer {st.session_state.token[:10]}...")
    print(f"Request data: {data}")
    
    # Make the request with explicit content type
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
    return None

def delete_document(document_id: str) -> bool:
    """Delete a document with authentication"""
    # First get the document details to get the filename
    documents = get_documents()
    document = next((doc for doc in documents if doc['id'] == document_id), None)
    
    if not document:
        print(f"Document with ID {document_id} not found")
        return False
    
    # Now delete using the filename and document_id to ensure folder cleanup
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

# UI Components
# Add at the very top, after imports
st.set_page_config(
    page_title="SmartDoc AI",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

def load_css():
    css_path = os.path.join(os.path.dirname(__file__), "styles.css")
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

def render_login_page():
    """Render the login page"""
    st.markdown('<h1 class="main-header">🤖 SmartDoc AI</h1>', unsafe_allow_html=True)
    

    # Center the login form
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div class="info-box">👋 New user? Please sign up before attempting to log in.</div>', unsafe_allow_html=True)
        
        with st.form("login_form", clear_on_submit=True):
            st.markdown('<h2 class="sub-header">🔐 Login</h2>', unsafe_allow_html=True)
            email = st.text_input("📧 Email")
            password = st.text_input("🔑 Password", type="password")
            submit = st.form_submit_button("Login", use_container_width=True)
            
            if submit:
                if login(email, password):
                    st.session_state.current_page = "main"
                    st.rerun()
        
        st.markdown("---")
        if st.button("📝 Don't have an account? Sign up", use_container_width=True):
            st.session_state.current_page = "signup"
            st.rerun()

def render_signup_page():
    """Render the signup page"""
    st.markdown('<h1 class="main-header">🤖 SmartDoc AI</h1>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("signup_form", clear_on_submit=True):
            st.markdown('<h2 class="sub-header">📝 Sign Up</h2>', unsafe_allow_html=True)
            email = st.text_input("📧 Email")
            username = st.text_input("👤 Username")
            password = st.text_input("🔑 Password", type="password")
            confirm_password = st.text_input("🔄 Confirm Password", type="password")
            submit = st.form_submit_button("Sign Up", use_container_width=True)
            
            if submit:
                if password != confirm_password:
                    st.error("⚠️ Passwords do not match")
                elif not email or not username or not password:
                    st.error("⚠️ All fields are required")
                else:
                    if signup(email, username, password):
                        st.session_state.current_page = "login"
                        st.rerun()
        
        st.markdown("---")
        if st.button("🔐 Already have an account? Log in", use_container_width=True):
            st.session_state.current_page = "login"
            st.rerun()

def render_main_app():
    """Render the main application after authentication"""
    # Enhanced sidebar with better styling
    with st.sidebar:
        st.markdown("""
            <div style="padding: 1rem; background-color: #f0f2f6; border-radius: 0.5rem; margin-bottom: 1rem;">
                <h3 style="color: #1E88E5; margin: 0;">👋 Welcome!</h3>
                <p style="margin: 0.5rem 0;">{}</p>
            </div>
        """.format(st.session_state.username), unsafe_allow_html=True)
        
        # --- Moved Upload UI to Sidebar ---
        st.markdown('<h2 class="sub-header">📤 Upload Document</h2>', unsafe_allow_html=True)
        st.markdown('<div class="info-box">📝 Supported formats: PDF, TXT, DOCX</div>', unsafe_allow_html=True)
        
        uploaded_file = st.file_uploader("Choose a file", type=["pdf", "txt", "docx"])
        
        if uploaded_file is not None:
            st.markdown(f"""
                <div style="padding: 1rem; background-color: #E3F2FD; border-radius: 0.5rem; margin: 1rem 0;">
                    <p><strong>Selected file:</strong> {uploaded_file.name}</p>
                    <p><strong>Type:</strong> {uploaded_file.type}</p>
                </div>
            """, unsafe_allow_html=True)
            
            if st.button("📤 Upload Document", use_container_width=True):
                with error_boundary(), st.spinner("📤 Uploading document..."):
                    result = upload_document(uploaded_file)  # error_boundary will auto-catch exceptions
                    if result and not result.get("detail"):
                        st.success("✅ Document uploaded successfully!")
                        st.session_state.force_refresh = True  # Changed from full rerun
                    elif result and result.get("detail"):
                        st.error(f"❌ {result['detail']}")
                    else:
                        st.error("❌ Upload failed. Please check the console for details.")
        # --- End Upload UI in Sidebar ---

        if st.button("🚪 Logout", use_container_width=True):
            logout()
            st.rerun()
    
    # Only one tab now: My Documents
    st.markdown('<h2 class="sub-header">📚 My Documents</h2>', unsafe_allow_html=True)
    documents = get_documents()
    
    if not documents:
        st.markdown("""
            <div class="info-box" style="text-align: center;">
                <h3>📝 No documents found</h3>
                <p>Upload a document to get started!</p>
            </div>
        """, unsafe_allow_html=True)
    else:
        # Add search/filter functionality
        search_term = st.text_input("🔍 Search documents", "")
        filtered_docs = [doc for doc in documents if search_term.lower() in doc['filename'].lower()]

        # Sort documents by upload_time (descending)
        filtered_docs.sort(
            key=lambda doc: doc.get('upload_time', ''),
            reverse=True
        )

        # Pagination controls
        items_per_page = 5
        total_pages = max(1, (len(filtered_docs) + items_per_page - 1) // items_per_page)
        page_number = st.number_input("Page", 1, total_pages, key="doc_page", format="%d")
        start_idx = (page_number - 1) * items_per_page
        end_idx = start_idx + items_per_page

        for doc in filtered_docs[start_idx:end_idx]:
            with st.expander(f"📄 {doc['filename']}", expanded=False):
                # Create a column layout for filename and delete button
                col_header = st.columns([4, 1])
                
                with col_header[0]:
                    # Show upload date and time
                                    # Cache formatted times
                    if 'time_cache' not in st.session_state:
                        st.session_state.time_cache = {}

                    doc_id = doc['id']
                    if doc_id not in st.session_state.time_cache:
                        upload_time = doc.get('upload_time')
                        if upload_time:
                            try:
                                if upload_time.endswith('Z'):
                                    utc_time = datetime.fromisoformat(upload_time[:-1]).replace(tzinfo=timezone.utc)
                                else:
                                    utc_time = datetime.fromisoformat(upload_time).replace(tzinfo=timezone.utc)
                                ist = pytz.timezone('Asia/Kolkata')
                                ist_time = utc_time.astimezone(ist)
                                formatted_time = ist_time.strftime('%Y-%m-%d %H:%M:%S %Z')
                            except Exception as e:
                                print(f"Error formatting time: {e}")
                                formatted_time = str(upload_time)
                            st.session_state.time_cache[doc_id] = formatted_time
                        else:
                            st.session_state.time_cache[doc_id] = "Unknown time"

                    st.markdown(f'<div style="color: #888; margin-bottom: 0.5rem;">🕒 Uploaded: {st.session_state.time_cache[doc_id]}</div>', unsafe_allow_html=True)
                
                with col_header[1]:
                    if st.button("🗑️ Delete", 
                               key=f"del_{doc['id']}", 
                               use_container_width=True,
                               help="Delete this document"):
                        with st.spinner("🗑️ Deleting..."):
                            if delete_document(doc['id']):
                                st.success("✅ Document deleted successfully!")
                                st.session_state.force_refresh = True
                                st.rerun()
                            else:
                                st.error("❌ Delete failed")
                # Enhanced status display
                is_vectorized = doc.get('is_vectorized', False)
                status_icon = "✅" if is_vectorized else "⏳"
                status_color = "#4CAF50" if is_vectorized else "#FF5722"
                status_text = "Vectorized" if is_vectorized else "Pending Vectorization"
                st.markdown(f"""
                    <div style="margin-bottom: 1rem;">
                        <span style="color: {status_color}; font-weight: bold;">
                            {status_icon} {status_text}
                        </span>
                    </div>
                """, unsafe_allow_html=True)
                
                # Action buttons in columns with enhanced styling
                col1, col2 = st.columns([1, 1])  # Only two columns now
                
                with col1:
                    vectorize_button = st.button(
                        "🧠 Vectorize" if not is_vectorized else "✅ Vectorized",
                        key=f"vec_{doc['id']}",
                        disabled=is_vectorized,
                        use_container_width=True
                    )
                    if vectorize_button:
                        with st.spinner("🧠 Vectorizing..."):
                            result = vectorize_document(doc['id'])
                            if result:
                                if "message" in result:
                                    st.info(result["message"])
                                else:
                                    st.success("✨ Document vectorized successfully!")
                                st.session_state.force_refresh = True
                                st.rerun()
                
                with col2:
                    has_summary = bool(doc.get('summary'))
                    summarize_disabled = not is_vectorized and not has_summary
                    
                    if st.button(
                        "📝 View Summary" if has_summary else "✨ Summarize",
                        key=f"sum_{doc['id']}",
                        disabled=summarize_disabled,
                        use_container_width=True
                    ):
                        if has_summary:
                            st.markdown("""
                                <div class="summary-container">
                                    <h4>📝 Document Summary</h4>
                                    {}
                                </div>
                            """.format(doc.get('summary', 'No summary available')), unsafe_allow_html=True)
                        else:
                            with st.spinner("✨ Generating summary..."):
                                result = summarize_document(doc['id'])
                                if result:
                                    if result.get('error'):
                                        st.error(f"❌ {result.get('summary')}")
                                    else:
                                        st.success("✅ Summary generated!")
                                        st.session_state.force_refresh = True
                                        st.rerun()  # Add this back but with cache refresh
                                        st.markdown("""
                                            <div class="summary-container">
                                                <h4>📝 Document Summary</h4>
                                                {}
                                            </div>
                                        """.format(result.get('summary')), unsafe_allow_html=True)
                    
                # Export summary button (remains inside expander, but outside columns)
                if has_summary:
                    st.download_button(
                        label="⬇️ Export Summary as TXT",
                        data=export_summary_as_txt(doc.get('summary', ''), doc.get('filename', f"document_{doc['id']}.txt")),
                        file_name=f"summary_{doc.get('filename', 'document_' + str(doc['id']))}.txt",
                        mime="text/plain",
                        key=f"export_sum_{doc['id']}"
                    )
                
                # Enhanced chat interface
                if is_vectorized and st.checkbox("💬 Enable Chat", key=f"chat_{doc['id']}"):
                    st.markdown("""
                        <div style="margin-top: 2rem; padding: 1rem; background-color: #F5F5F5; border-radius: 0.5rem;">
                            <h3 style="color: #1E88E5;">💬 Chat with Document</h3>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    question = st.text_input("🤔 Ask a question:", key=f"q_{doc['id']}")
                    if st.button("🔍 Ask", key=f"ask_{doc['id']}", use_container_width=True):
                        if not question or question.strip() == "":
                            st.error("❌ Please enter a question before asking")
                        else:
                            with st.spinner("🤔 Thinking..."):
                                # Check if document is actually vectorized by looking for embeddings
                                result = ask_question(doc['id'], question)
                                if result:
                                    st.markdown("""
                                        <div style="margin-top: 1rem; padding: 1rem; background-color: #E8F5E9; border-radius: 0.5rem;">
                                            <h4 style="color: #2E7D32;">💡 Answer:</h4>
                                            <p>{}</p>
                                        </div>
                                    """.format(result.get('answer', 'No answer available')), unsafe_allow_html=True)
                                else:
                                    st.info("⚠️ Vectorize the document to enable chat functionality")
                                    
                st.markdown("<hr style='margin: 2rem 0;'>", unsafe_allow_html=True)

# Main app flow
def main():
    load_css()
    if st.session_state.current_page == "login":
        render_login_page()
    elif st.session_state.current_page == "signup":
        render_signup_page()
    elif st.session_state.current_page == "main":
        if st.session_state.authenticated:
            render_main_app()
        else:
            st.session_state.current_page = "login"
            st.rerun()

if __name__ == "__main__":
    main()

import streamlit as st
from datetime import datetime, timezone
import pytz  # You'll need to add pytz to requirements.txt
from frontend_utils import *


from contextlib import contextmanager

@contextmanager
def error_boundary():
    try:
        yield
    except Exception as e:
        st.error(f"Operation failed: {str(e)}")
        st.stop()


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

# UI Components

st.set_page_config(
    page_title="SmartDoc AI",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Then continue with your existing code...
def load_css():
    """Loads custom CSS for styling the Streamlit app."""
    # Ensure styles.css is in the correct path or make it accessible
    try:
        with open('app/frontend/styles.css') as f: # Assuming styles.css is in the same directory as app.py
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
    except FileNotFoundError:
        st.warning("styles.css not found. App will run without custom styling.")
    except Exception as e:
        st.error(f"Error loading CSS: {e}")


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
               # --- MODIFIED: Use the new wait_for_backend function ---
                with st.spinner("Backend waking up, please wait... This may take up to a minute."):
                    if not wait_for_backend(): # Wait up to 10 seconds (default in function)
                        st.error("Backend did not wake up in time. Please reload the tab and try loggin in again")
                        st.stop() # Stop further execution if backend is not responsive
                # --- END MODIFIED ---
                if login(email, password):
                    st.session_state.current_page = "main"
                    st.rerun()
        
        st.markdown("---")
        if st.button("📝 Don't have an account? Sign up", use_container_width=True):
            st.session_state.current_page = "signup"
            st.rerun()




def render_signup_page():
    """Render the signup page, now with Gemini API Key input."""
    st.markdown('<h1 class="main-header">🤖 SmartDoc AI</h1>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("signup_form", clear_on_submit=True):
            st.markdown('<h2 class="sub-header">📝 Sign Up</h2>', unsafe_allow_html=True)
            email = st.text_input("📧 Email")
            username = st.text_input("👤 Username")
            password = st.text_input("🔑 Password", type="password")
            confirm_password = st.text_input("🔄 Confirm Password", type="password")

            # --- MODIFIED SECTION FOR GEMINI API KEY INSTRUCTIONS ---
            st.info(
                """
                **How to get your Gemini API Key:**
                1. Go to Google AI Studio at https://makersuite.google.com/app/apikey
                2. If prompted, sign in with your Google account.
                3. Click on **'Create API Key'** or select an existing one.
                4. Copy the generated API key and paste it below.
                """
            )
            #  Input for Gemini API Key
            gemini_api_key = st.text_input(
                "🔑 Gemini API Key", 
                type="password", 
                help="Your personal Gemini API key. Get it from Google AI Studio: https://makersuite.google.com/app/apikey"
            )
            submit = st.form_submit_button("Sign Up", use_container_width=True)
            
            if submit:
                if password != confirm_password:
                    st.error("⚠️ Passwords do not match.")
                elif not email or not username or not password or not gemini_api_key: # NEW: check for gemini_api_key
                    st.error("⚠️ All fields, including Gemini API Key, are required.")
                else:

                    # --- MODIFIED: Use the new wait_for_backend function ---
                    with st.spinner("Backend waking up, please wait... This may take up to a minute."):
                        if not wait_for_backend(): # Wait up to 60 seconds (default in function)
                            st.error("Backend did not wake up in time. Please try again shortly or check server status.")
                            st.stop() # Stop further execution if backend is not responsive
                    # --- END MODIFIED ---

                    # NEW: Pass gemini_api_key to the signup function
                    if signup(email, username, password, gemini_api_key):  
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
                                        
                    
                # Export summary button (remains inside expander, but outside columns)
                if has_summary:
                    st.download_button(
                        label="⬇️ Export Summary as TXT",
                        data=export_summary_as_txt(doc.get('summary', ''), doc.get('filename', f"document_{doc['id']}.txt")),
                        file_name=f"summary_{doc.get('filename', f'document_{doc['id']}')}.txt",
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

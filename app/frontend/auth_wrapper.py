import requests
from typing import Optional
from streamlit import cache_data

def authenticated_request(method, endpoint: str, json: Optional[dict] = None, headers: Optional[dict] = None) -> Optional[requests.Response]:
    """Make authenticated API request with JWT from environment
    Returns response object or None if failed
    """
    import os
    token = os.getenv("JWT_TOKEN") 
    if not token:
        print("No JWT token found in environment. This might be expected if running frontend only.")
        pass # Allow to proceed if token not found, as frontend_utils handles auth

    if headers is None:
        headers = {}
    if token: # Only add header if token is available
        headers["Authorization"] = f"Bearer {token}"
    
    try:
        response = method(endpoint, json=json, headers=headers)
        return response
    except Exception as e:
        print(f"Request failed: {str(e)}")
        return None

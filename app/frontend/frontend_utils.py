import requests
from typing import List
import io
from streamlit import cache_data
from auth_wrapper import authenticated_request


@cache_data(ttl=300)  # <-- Add decorator with correct parameters
def export_summary_as_txt(summary: str, filename: str) -> str:
    """Export summary as TXT"""
    txt_bytes = io.BytesIO()
    txt_bytes.write(f"Summary of {filename}\n\n".encode("utf-8"))
    txt_bytes.write(summary.encode("utf-8"))
    txt_bytes.seek(0)
    return f"Summary for {filename}:\n\n{summary}"




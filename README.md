SmartDoc AI 🧠📄
A Document Intelligence Platform with RAG-powered Q&A, Summarization, and Admin Control

SmartDoc AI is a Retrieval-Augmented Generation (RAG) tool designed to extract, summarize, and intelligently answer questions from your documents—all while ensuring minimal hallucination and complete local control.

🚀 Features
✅ Precision Answers — Only from uploaded documents, not hallucinated
✅ Multi-Format Support — PDF, DOCX, and TXT supported
✅ Hierarchical Summarization — Summarizes even large documents
✅ Semantic Q&A — Natural queries with source-cited responses
✅ Privacy First — User data never leaves your environment
✅ Admin Dashboard — Manage users and files with ease

🛠 Tech Stack
🔧 Backend
FastAPI (RESTful APIs)

SQLModel + SQLite/PostgreSQL

Gemini 1.5 (LLM API)

TF-IDF + Cosine Similarity

PyMuPDF + python-docx (text extraction)

💻 Frontend
Streamlit (UI)

Custom CSS

📦 Installation
Prerequisites
Python 3.9+

Your own Google Gemini API Key

Optional: PostgreSQL (default is SQLite)

🔧 Setup Instructions
Clone the repo

bash
Copy
Edit
git clone https://github.com/yourusername/smartdoc-ai.git
cd smartdoc-ai
Create virtual environment

bash
Copy
Edit
python -m venv smartdoc-ai_env
source smartdoc-ai_env/bin/activate  # On Windows: venv\Scripts\activate
Install dependencies

bash
Copy
Edit
pip install -r requirements.txt
Configure environment
Create a .env file with the following variables:

ini
Copy
Edit
GOOGLE_API_KEY=your_key_here
ADMIN_EMAIL=admin@example.com
ADMIN_USERNAME=admin
ADMIN_PASSWORD=securepassword
🧑‍💻 Running the App
Start the backend

bash
Copy
Edit
uvicorn app.main:app --reload
Start the frontend

bash
Copy
Edit
streamlit run app/app.py
Open http://localhost:8501 in your browser.

⚙️ Configuration
Variable	Description	Default
GOOGLE_API_KEY	Gemini LLM API key	Required
ADMIN_EMAIL	Admin account email	Required
UPLOAD_DIR	Uploaded file directory	uploaded_files
VECTOR_STORE_DIR	Vector store location	vector_stores
DATABASE_URL	SQLModel DB URL	sqlite:///db.sqlite

🎨 Theme Issues (Streamlit)
If you see a dark theme unexpectedly:

Click ☰ in top-right corner → Settings → Theme → Light → Save & refresh

☁️ Deployment Options
Supported platforms:

Railway (free-tier compatible)

Render

AWS Elastic Beanstalk

Docker

Docker
bash
Copy
Edit
docker build -t smartdoc-ai .
docker run -p 8501:8501 -p 8000:8000 smartdoc-ai
🤝 Contributing
Fork the repo

Create a new branch: git checkout -b feature/YourFeature

Commit changes: git commit -m "Add YourFeature"

Push: git push origin feature/YourFeature

Open a Pull Request

📜 License
MIT License. See LICENSE file.

📬 Contact
Project Maintainer: Arnav Kumar
📧 Email: Arnavu7038@gmail.com
🔗 GitHub: SmartDoc AI Repo
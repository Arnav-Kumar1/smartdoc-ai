# SmartDoc AI 🧠📄  
**A Document Intelligence Platform with RAG-powered Q&A, Summarization, and Admin Control**

SmartDoc AI is a Retrieval-Augmented Generation (RAG) tool designed to extract, summarize, and intelligently answer questions from your documents—all while ensuring minimal hallucination and complete local control.

---

## 🚀 Features

✅ **Precision Answers** — Only from uploaded documents, no AI hallucinations  
✅ **Multi-Format Support** — PDF, DOCX, and TXT files  
✅ **Hierarchical Summarization** — Handles even large documents  
✅ **Semantic Q&A** — Natural queries with source-cited responses  
✅ **Privacy First** — No data leaves your environment  
✅ **Admin Dashboard** — Manage users and files with full control  

---

## 🛠 Tech Stack

### 🔧 Backend
- FastAPI (RESTful APIs)  
- SQLModel + SQLite / PostgreSQL  
- Gemini 1.5 (LLM API)  
- TF-IDF + Cosine Similarity  
- PyMuPDF + python-docx (text extraction)

### 💻 Frontend
- Streamlit (UI)
- Custom CSS

---

## 📦 Installation

### Prerequisites
- Python 3.9+
- Your own [Google Gemini API Key](https://aistudio.google.com/app/apikey)
- Optional: PostgreSQL (SQLite used by default)

---

### 🔧 Setup Instructions

1. **Clone the repo**
```bash
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
Create and configure your .env file

ini
Copy
Edit
GOOGLE_API_KEY=your_key_here
ADMIN_EMAIL=admin@example.com
ADMIN_USERNAME=admin
ADMIN_PASSWORD=securepassword
🧑‍💻 Usage
Start the Backend
bash
Copy
Edit
uvicorn app.main:app --reload
Start the Frontend
bash
Copy
Edit
streamlit run app/app.py
Visit http://localhost:8501 in your browser.

⚙️ Configuration Variables
Variable	Description	Default
GOOGLE_API_KEY	Gemini LLM API key	Required
ADMIN_EMAIL	Admin email	Required
ADMIN_USERNAME	Admin username	Required
ADMIN_PASSWORD	Admin password	Required
UPLOAD_DIR	Uploaded file directory	uploaded_files
VECTOR_STORE_DIR	Vector store location	vector_stores
DATABASE_URL	SQLModel DB URL	sqlite:///db.sqlite

🖼 Theme Issues (Frontend)
If Streamlit defaults to a dark theme:

Click the ☰ icon (top-right)

Go to Settings → Theme

Select Light

Click Save and refresh

☁️ Deployment
SmartDoc AI supports deployment on:

Railway (free tier)

Render

AWS Elastic Beanstalk

Docker

Docker Example

docker build -t smartdoc-ai .
docker run -p 8501:8501 -p 8000:8000 smartdoc-ai
🤝 Contributing
Fork the repository

Create a new branch:


git checkout -b feature/YourFeature
Commit your changes:


git commit -m "Add YourFeature"
Push to the branch:


git push origin feature/YourFeature
Open a Pull Request

📜 License
This project is licensed under the MIT License. See the LICENSE file for details.

📬 Contact
Maintainer: Arnav Kumar
📧 Email: Arnavu7038@gmail.com
🔗 Project Repo: github.com/Arnav-Kumar1/smartdoc-ai
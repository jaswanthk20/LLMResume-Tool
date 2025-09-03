# llm_utils.py
import os
import requests
import json
import re
from pathlib import Path
import fitz
from docxtpl import DocxTemplate

# ---- OLLAMA CONFIG ----
# Defaults work on bare‑metal Windows; override via env when in Docker/Azure.
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma:2b")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "90"))

def ask_ollama_gemma(prompt, model: str = None):
    base = OLLAMA_BASE_URL.rstrip("/")
    model = model or OLLAMA_MODEL
    url = f"{base}/api/generate"
    try:
        resp = requests.post(
            url,
            headers={"Content-Type": "application/json"},
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=OLLAMA_TIMEOUT,
        )
        print(f"[DEBUG] POST {url} -> {resp.status_code}")
        print(f"[DEBUG] Ollama raw: {resp.text[:1000]}")
        resp.raise_for_status()
        data = resp.json()
        # Ollama returns {"response": "..."} where the inner text is your model output.
        return data.get("response", "")
    except requests.exceptions.RequestException as e:
        return f"[LLM ERROR] Request to Ollama failed: {e}"

def extract_text_from_pdf(pdf_content: bytes) -> str:
    try:
        doc = fitz.open(stream=pdf_content, filetype="pdf")
        text = "".join(p.get_text() for p in doc)
        doc.close()
        return text.strip()
    except Exception as e:
        return f"[PDF PARSE ERROR] {e}"

def extract_resume_fields(parsed_text: str) -> str:
    prompt = f"""
Return ONLY valid JSON (no backticks).
Fields:
- name: string
- professional_summary: string
- professional_experience: list of {{title, company, dates, description}}
- education: list of {{degree, institution, dates}}
- certification_&_specialized_training: list of {{name, issuer, date}}
- skills: list of strings

Resume Text:
\"\"\"{parsed_text}\"\"\"
"""
    print("[INFO] Sending parsed text to Gemma 3 via Ollama...")
    return ask_ollama_gemma(prompt)

def parse_llm_response(response_text: str) -> dict:
    # Try strict JSON first
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        pass
    # Fallback: extract first JSON object
    m = re.search(r'\{[\s\S]*\}', response_text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError as e:
            print(f"[WARN] JSON decode failed: {e}")
    print("[WARN] Could not parse LLM output as JSON")
    return {}

def fill_docx_template(data: dict, output_path: Path, template_path: Path):
    doc = DocxTemplate(str(template_path))
    context = {
        "name": data.get("name", "N/A"),
        "professional_summary": data.get("professional_summary", "No summary."),
        "skills": ", ".join(data.get("skills", [])) if isinstance(data.get("skills", list)) else data.get("skills", ""),
        "professional_experience": data.get("professional_experience", []),
        "education": data.get("education", []),
        "certification_specialized_training": data.get("certification_&_specialized_training", []),
    }
    doc.render(context)
    doc.save(str(output_path))
    print(f"[INFO] DOCX saved to {output_path}")

def process_pdf(uploaded_file):
    pdf_bytes = uploaded_file.read()
    parsed_text = extract_text_from_pdf(pdf_bytes)
    if parsed_text.startswith("[PDF PARSE ERROR]"):
        return parsed_text, "", {}

    llm_response = extract_resume_fields(parsed_text)
    print("[DEBUG] Raw LLM response:\n", llm_response)

    if llm_response.startswith("[LLM ERROR]") or "[PARSE ERROR]" in llm_response:
        print("[ERROR] LLM failed: ", llm_response)
        return llm_response, "", {}

    data = parse_llm_response(llm_response)
    if not data:
        return "Failed to parse LLM response into JSON.", "", {}

    # Use MEDIA, not static
    media_dir = Path(os.getenv("MEDIA_ROOT", Path(__file__).resolve().parent.parent / "media"))
    media_dir.mkdir(parents=True, exist_ok=True)

    output_docx_path = media_dir / "filled_resume.docx"

    # Make sure the template path matches your actual template location.
    # If your templates/ is at project root (same level as manage.py), use BASE_DIR / "templates"
    project_root = Path(__file__).resolve().parent.parent  # adjust if your layout differs
    template_path = project_root / "templates" / "Final Template.docx"

    fill_docx_template(data, output_docx_path, template_path)

    return (
        llm_response,
        "/media/" + output_docx_path.name,
        data,
    )

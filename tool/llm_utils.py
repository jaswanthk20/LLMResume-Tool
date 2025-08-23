import fitz  # PyMuPDF
import requests
import re
from pathlib import Path
from docxtpl import DocxTemplate
import os
import json

# PDF Extraction
def extract_text_from_pdf(pdf_content):
    try:
        doc = fitz.open(stream=pdf_content, filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        print("[INFO] PDF text extraction complete.")
        return text.strip()
    except Exception as e:
        return f"[PDF PARSE ERROR] {e}"

# Gemma 3 via Ollama API call
def ask_ollama_gemma(prompt, model="gemma3:latest"):
    url = "http://localhost:11434/api/generate"
    headers = {"Content-Type": "application/json"}
    data = {
        "model": model,
        "prompt": prompt,
        "stream": False
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        print(f"[DEBUG] Ollama status: {response.status_code}")
        print(f"[DEBUG] Ollama raw response: {response.text[:1000]}")

        if response.status_code == 200:
            return response.json()["response"]
        else:
            return f"[LLM ERROR] {response.status_code}: {response.text}"
    except requests.exceptions.RequestException as e:
        return f"[LLM ERROR] Request to Ollama failed: {e}"

# Extract structured fields
def extract_resume_fields(parsed_text):
    prompt = f"""
You are an expert resume parser. Based on the following resume text, extract the information for the fields:
"name", "professional_summary", "professional_experience", "education", "certification_&_specialized_training", and "skills".

For "professional_experience", "education", and "certification_&_specialized_training", return a LIST of dictionaries, where each dictionary represents an entry and contains relevant sub-fields (e.g., for experience: "title", "company", "dates", "description"; for education: "degree", "institution", "dates").
For "skills", return a LIST of strings.
For "professional_summary" and "name", return a single string.

Resume Text:
\"\"\"
{parsed_text}
\"\"\"
"""
    print("[INFO] Sending parsed text to Gemma 3 via Ollama...")
    return ask_ollama_gemma(prompt)

# Parse JSON safely
def parse_llm_response(response_text):
    json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError as e:
            print(f"[WARN] Failed to decode LLM JSON response: {e}")
            print(f"[DEBUG] Malformed JSON: {json_match.group(0)}")
    print("[WARN] Failed to decode LLM response.")
    print(f"[DEBUG] Full response: {response_text}")
    return {}

# Fill DOCX template
def fill_docx_template(data, output_path, template_path=Path(__file__).parent / "templates" / "Final Template.docx"):
    doc = DocxTemplate(str(template_path))
    context = {
        "name": data.get("name", "N/A"),
        "professional_summary": data.get("professional_summary", "No summary."),
        "skills": ", ".join(data.get("skills", [])) if isinstance(data.get("skills", []), list) else data.get("skills", ""),
        "professional_experience": data.get("professional_experience", []),
        "education": data.get("education", []),
        "certification_specialized_training": data.get("certification_&_specialized_training", []),
    }
    doc.render(context)
    doc.save(str(output_path))
    print(f"[INFO] DOCX saved to {output_path}")

# Main pipeline
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

    output_dir = Path(__file__).parent / "static"
    output_docx_path = output_dir / "filled_resume.docx"
    fill_docx_template(data, output_docx_path)

    return (
        llm_response,
        "/static/" + output_docx_path.name,
        data,
    )


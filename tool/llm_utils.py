import fitz  # PyMuPDF
import requests
import re
import zipfile
from pathlib import Path
from tempfile import NamedTemporaryFile
from docxtpl import DocxTemplate
import json

OPENROUTER_API_KEY = "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"

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

def ask_online_llm(prompt, model="mistralai/mistral-7b-instruct"):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
    }

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
        )
        print(f"[INFO] LLM request status: {response.status_code}")
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"].strip()
        else:
            return f"[LLM ERROR] {response.status_code}: {response.text}"
    except Exception as e:
        return f"[LLM ERROR] {e}"

def extract_resume_fields(parsed_text):
    prompt = f"""
You are an expert resume parser. Based on the following resume text, extract the information for the fields: "name", "professional_summary", "professional_experience", "education", "certification_&_specialized_training", and "skills".

Return the response as a single, minified JSON object. The keys in the JSON should match the field names provided.

Resume Text:
\"\"\"
{parsed_text}
\"\"\"
"""
    return ask_online_llm(prompt)

def parse_resume_from_pdf(pdf_content):
    print(f"[INFO] Reading PDF content")
    parsed_text = extract_text_from_pdf(pdf_content)
    if parsed_text and parsed_text.startswith("[PDF PARSE ERROR]"):
        return parsed_text
    print("[INFO] Sending text to LLM...")
    return extract_resume_fields(parsed_text)

def parse_llm_response(response_text):
    try:
        # Find the JSON object in the response string
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            return json.loads(json_str)
        else:
            print("[WARN] No JSON object found in the LLM response.")
            return {}
    except json.JSONDecodeError as e:
        print(f"[ERROR] Failed to decode JSON from LLM response: {e}")
        return {}
    except Exception as e:
        print(f"[ERROR] An unexpected error occurred in parse_llm_response: {e}")
        return {}

def fill_docx_template(
    data,
    output_path,
    template_path=Path(__file__).parent / "templates" / "Final Template.docx",
):
    doc = DocxTemplate(str(template_path))
    context = {
        "name": data.get("name", ""),
        "professional_summary": data.get("professional_summary", ""),
        "skills": data.get("skills", ""),
    }

    doc.render(context)

    def escape_xml(text: str) -> str:
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    def multiline_to_xml(text: str) -> str:
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if not lines:
            return ""
        xml_lines = [
            f"<w:p><w:r><w:t>{escape_xml(ln)}</w:t></w:r></w:p>" for ln in lines
        ]
        return "".join(xml_lines)

    with NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
        temp_path = Path(tmp.name)
    doc.save(temp_path)

    block_patterns = {
        "education": r"<w:t>{% for ed in education %}</w:t>[\s\S]*?<w:t xml:space=\"preserve\"> %}</w:t>",
        "professional_experience": r"<w:t>{% for e in experience %}</w:t>[\s\S]*?<w:t xml:space=\"preserve\"> %}</w:t>",
        "certification_&_specialized_training": r"<w:t>{% for c in certifications %}</w:t>[\s\S]*?<w:t xml:space=\"preserve\"> %}</w:t>",
        "skills": r"<w:t>{% for s in skills %}</w:t>[\s\S]*?<w:t xml:space=\"preserve\"> %}</w:t>",
    }

    with zipfile.ZipFile(temp_path) as zin, zipfile.ZipFile(output_path, "w") as zout:
        for item in zin.infolist():
            content = zin.read(item.filename)
            if item.filename == "word/document.xml":
                text = content.decode("utf-8")
                for key, pattern in block_patterns.items():
                    replacement = multiline_to_xml(data.get(key, ""))
                    text = re.sub(pattern, replacement, text, flags=re.DOTALL)
                content = text.encode("utf-8")
            zout.writestr(item, content)

    temp_path.unlink(missing_ok=True)

def save_parsed_data(data, output_dir, basename="parsed_resume"):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{basename}.json"

    with open(json_path, "w", encoding="utf-8") as jf:
        json.dump(data, jf, ensure_ascii=False, indent=2)

    return json_path

def process_pdf(uploaded_file):
    pdf_bytes = uploaded_file.read()
    llm_response = parse_resume_from_pdf(pdf_bytes)
    data = parse_llm_response(llm_response)

    output_path = Path(__file__).parent / "static" / "Final Template.docx"
    fill_docx_template(data, output_path)

    base_name = Path(uploaded_file.name).stem or "parsed_resume"
    json_path = save_parsed_data(data, Path(__file__).parent / "static", base_name)

    return (
        llm_response,
        "/static/" + output_path.name,
        data,
        "/static/" + json_path.name,
    )

if __name__ == "__main__":
    try:
        with open(r"C:\Users\jaswa\Desktop\rfp_tool\resume1.pdf", "rb") as f:
            resume_content = f.read()
        result = parse_resume_from_pdf(resume_content)
    except FileNotFoundError:
        result = "Error: Dummy resume file not found."
    print("\n Parsed Resume Output:\n")
    print(result)
import fitz  # PyMuPDF
import requests
import re
import zipfile
from pathlib import Path
from tempfile import NamedTemporaryFile
from docxtpl import DocxTemplate
import json


def guess_address_from_text(text: str) -> str:
    """Heuristically guess an address from raw resume text."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    address_keywords = [
        "street",
        "st",
        "road",
        "rd",
        "avenue",
        "ave",
        "boulevard",
        "blvd",
        "drive",
        "dr",
        "lane",
        "ln",
        "court",
        "ct",
        "parkway",
        "pkwy",
        "circle",
        "cir",
        "way",
    ]

    # Limit search to the first few lines where contact info usually appears
    for line in lines[:10]:
        lower = line.lower()
        if any(k in lower for k in address_keywords) and re.search(r"\d", line):
            return line

    # Fallback pattern like "City, ST ZIP"
    city_state_zip = re.compile(r",\s*[A-Z]{2}\s+\S+")
    for line in lines[:10]:
        if city_state_zip.search(line):
            return line

    return ""


OPENROUTER_API_KEY = (
    "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"
)


def extract_text_from_pdf(pdf_content):
    # Extracting text content from a PDF file using PyMuPDF.
    # Accepts file content (bytes) instead of a path.

    try:
        # Use fitz.open with a file-like object created from bytes
        doc = fitz.open(stream=pdf_content, filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        print(
            "[INFO] PDF text extraction complete."
        )  # Diagnostic log for PDF extraction
        return text.strip()
    except Exception as e:
        return f"[PDF PARSE ERROR] {e}"


def ask_online_llm(prompt, model="mistralai/mistral-7b-instruct"):
    # Sending a prompt to LLM Model.

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
        print(
            f"[INFO] LLM request status: {response.status_code}"
        )  # Diagnostic log for LLM request status
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"].strip()
        else:
            return f"[LLM ERROR] {response.status_code}: {response.text}"
    except Exception as e:
        return f"[LLM ERROR] {e}"


def extract_resume_fields(parsed_text):
    # Extracts structured resume info using LLM from parsed resume text.

    prompt = f"""
You are an expert resume parser. Based on the following resume text, extract and structure the information into the following fields:

- Name
- Address (if any)
- Phone Number
- Email
- Professional Summary
- Professional Experience
- Education
- Certification & Specialized Training
<<<<<<< HEAD
- Technical Languages
=======
- Skills
>>>>>>> 9aaa1aee0f9507c7e0ebab4be0785b87a4f6e00d

Return the response in a clean format (no extra commentary).

Resume Text:
\"\"\"
{parsed_text}
\"\"\"
"""
    return ask_online_llm(prompt)


def parse_resume_from_pdf(pdf_content):
    # Parses resume and returns structured information
    # Accepts file content (bytes) instead of a path.

    print(f"[INFO] Reading PDF content")  # Diagnostic log for PDF content
    parsed_text = extract_text_from_pdf(pdf_content)
    if parsed_text and parsed_text.startswith("[PDF PARSE ERROR]"):
        return parsed_text
    print("[INFO] Sending text to LLM...")  # Diagnostic log for LLM request
    return extract_resume_fields(parsed_text)


def parse_llm_response(response_text):
    """Parse simple key/value pairs from the LLM output.

    The raw LLM output occasionally separates keys and values with tabs or
    multiple spaces instead of a colon.  This parser handles all of those
    cases so that fields like "Address (if any)" are captured reliably.
    """

    data: dict[str, str] = {}
    current_key: str | None = None

    lines = response_text.splitlines()
    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Match "Key: value", "Key\tvalue" or "Key    value" only when the line
        # begins with an alphabetic character. This avoids mistaking bullet
        # lines like "- 2020-2021: ..." for new keys.
        m = re.match(r"^([A-Za-z][^:\t]*?)(?::|\t|\s{2,})(.*)", line)
        if m:
            key = m.group(1).strip().lower().replace(" ", "_")
            value = m.group(2).strip()

            if value:
                data[key] = value
                current_key = None
            else:
                current_key = key
                data[current_key] = ""
        elif current_key:
            # Continuation of the previous key's value
            data[current_key] += ("\n" if data[current_key] else "") + line

    # Normalise some common keys for easier downstream usage
    if "address_(if_any)" in data and "address" not in data:
        data["address"] = data["address_(if_any)"]

    return data


def fill_docx_template(
    data,
    output_path,
    template_path=Path(__file__).parent / "templates" / "Final Template.docx",
):
    """Fill ``Final Template.docx`` using the parsed resume data.

    ``python-docx`` cannot reliably replace template placeholders when the
    underlying XML splits them across multiple ``w:t`` runs. ``docxtpl`` handles
    this scenario correctly, so we use it to render the basic fields and then
    post-process the remaining Jinja loops by simple text substitution.
    """

    # Render basic placeholders using docxtpl so markers split across XML runs
    # are properly handled.
    doc = DocxTemplate(str(template_path))
    context = {
        "name": data.get("name", ""),
        "address": data.get("address", ""),
        "phone": data.get("phone_number", ""),
        "email": data.get("email", ""),
        "linkedIn": data.get("linkedin", ""),
        "professional_summary": data.get("professional_summary", ""),
        "skills": data.get("skills", ""),
    }

    doc.render(context)

    def escape_xml(text: str) -> str:
        """Escape text for inclusion in the Word XML."""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    def multiline_to_xml(text: str) -> str:
        """Convert newline separated text to a series of simple paragraphs."""
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if not lines:
            return ""
        xml_lines = [
            f"<w:p><w:r><w:t>{escape_xml(ln)}</w:t></w:r></w:p>" for ln in lines
        ]
        return "".join(xml_lines)

    # Save to a temporary file so we can post-process the XML to inject
    # sections like experience and education that are stored as raw strings.
    with NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
        temp_path = Path(tmp.name)
    doc.save(temp_path)

    # Replace block placeholders for sections that cannot be handled by
    # ``docxtpl`` because the Jinja markers are split across multiple ``w:t``
    # runs.  The patterns below match from the opening ``{% for ... %}`` tag to
    # the closing ``%}``, spanning any intermediate XML.
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
    """Save parsed resume data to a JSON file and return its path."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / f"{basename}.json"

    with open(json_path, "w", encoding="utf-8") as jf:
        json.dump(data, jf, ensure_ascii=False, indent=2)

    return json_path


def process_pdf(uploaded_file):
    """Process an uploaded PDF file and generate a formatted DOCX and JSON.

    Returns the raw LLM response, the public paths to the generated DOCX and
    JSON file, and the parsed data dictionary for further use (e.g. displaying
    on the success page).
    """
    pdf_bytes = uploaded_file.read()
    llm_response = parse_resume_from_pdf(pdf_bytes)
    data = parse_llm_response(llm_response)

    parsed_text = extract_text_from_pdf(pdf_bytes)

    # If the LLM failed to detect an address, try to guess it from the PDF text
    if not data.get("address"):
        guessed = guess_address_from_text(parsed_text)
        if guessed:
            data["address"] = guessed
            data["address_(if_any)"] = guessed


    # Write the filled template to the public static folder so it can be
    # downloaded via the Django app.  Save using the same file name as the
    # template to preserve the expected format.
    output_path = Path(__file__).parent / "static" / "Final Template.docx"
    fill_docx_template(data, output_path)

    # Also persist the parsed data as JSON for later use
    base_name = Path(uploaded_file.name).stem or "parsed_resume"
    json_path = save_parsed_data(
        data, Path(__file__).parent / "static", base_name
    )

    return (
        llm_response,
        "/static/" + output_path.name,
        data,
        "/static/" + json_path.name,
    )


# Output Section
if __name__ == "__main__":
    # Example usage with a dummy byte string (replace with actual file reading)
    # In a real scenario, you would read the uploaded file into a bytes object.
    try:
        with open(r"C:\Users\jaswa\Desktop\rfp_tool\resume1.pdf", "rb") as f:
            resume_content = f.read()
        result = parse_resume_from_pdf(resume_content)
    except FileNotFoundError:
        result = "Error: Dummy resume file not found."
    print("\n Parsed Resume Output:\n")
    print(result)

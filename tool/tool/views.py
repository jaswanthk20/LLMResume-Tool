from django.shortcuts import render, redirect

# Import llm_utils explicitly from the project package.
import llm_utils

def uploadpage(request):
    if request.method == 'POST':
        if 'resume_file' not in request.FILES:
            return render(request, 'upload.html', {'error': 'No file was uploaded.'})

        uploaded_file = request.FILES['resume_file']
        if not uploaded_file.name.endswith('.pdf'):
            return render(request, 'upload.html', {'error': 'Please upload a valid PDF file.'})

        try:
            llm_text, docx_path, parsed_data = llm_utils.process_pdf(uploaded_file)
            request.session['llm_processing_results'] = llm_text
            request.session['generated_docx'] = docx_path
            request.session['parsed_results'] = parsed_data
            return redirect('/uploadsuccess/')
        except Exception as e:
            return render(request, 'upload.html', {'error': f'An error occurred: {e}'})

    return render(request, 'upload.html')


def uploadsuccess(request):
    processing_results = request.session.pop('llm_processing_results', "No results found.")
    docx_path = request.session.pop('generated_docx', None)
    parsed_results = request.session.pop('parsed_results', {})

    def format_experience(items):
        lines = []
        for item in items:
            title = item.get("title", "").strip()
            dates = item.get("dates", "").strip()
            description = item.get("description", "").strip()
            header = f"{title} ({dates})" if title and dates else title or dates
            lines.append(f"{header}\n{description}" if header else description)
        return "\n\n".join(lines)

    def format_education(items):
        lines = []
        for item in items:
            degree = item.get("degree", "").strip()
            institution = item.get("institution", "").strip()
            dates = item.get("dates", "").strip()
            lines.append(f"{degree} at {institution} ({dates})".strip(" ()"))
        return "\n\n".join(lines)

    def format_certifications(items):
        lines = []
        for item in items:
            name = item.get("name", "").strip()
            date = item.get("date", "").strip()
            lines.append(f"{name} ({date})" if name and date else name or date)
        return "\n\n".join(lines)

    formatters = {
        "professional_experience": format_experience,
        "education": format_education,
        "certification_&_specialized_training": format_certifications,
        "skills": lambda items: ", ".join(items),
    }

    table_data = []
    if isinstance(parsed_results, dict):
        for label, key in [
            ('Name', 'name'),
            ('Professional Summary', 'professional_summary'),
            ('Skills', 'skills'),
            ('Professional Experience', 'professional_experience'),
            ('Education', 'education'),
            ('Certification & Specialized Training', 'certification_&_specialized_training'),
        ]:
            value = parsed_results.get(key)
            if value and key in formatters:
                value = formatters[key](value)
            elif not isinstance(value, str):
                value = str(value) if value is not None else ""
            table_data.append({'label': label, 'value': value})

    context = {
        'llm_results': processing_results,
        'docx_path': docx_path,
        'table_data': table_data,
    }
    return render(request, 'upload_success.html', context)

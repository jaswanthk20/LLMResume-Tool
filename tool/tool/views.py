from django.shortcuts import render, redirect

# Import llm_utils explicitly from the project package.
import llm_utils

def uploadpage(request):
    if request.method == 'POST':
        if 'resume_file' in request.FILES:
            uploaded_file = request.FILES['resume_file']

            (
                llm_text,
                docx_path,
                parsed_data,
            ) = llm_utils.process_pdf(uploaded_file)

            request.session['llm_processing_results'] = llm_text
            request.session['generated_docx'] = docx_path
            request.session['parsed_results'] = parsed_data

            print("File upload handled and processed")
            return redirect('/uploadsuccess/')
        else:
            print("No file uploaded or incorrect input name")
            return render(request, 'upload.html', {'error': 'Please upload a PDF file.'})

    return render(request, 'upload.html')


def uploadsuccess(request):
    processing_results = request.session.pop('llm_processing_results', None)
    docx_path = request.session.pop('generated_docx', None)
    parsed_results = request.session.pop('parsed_results', None)

    def flatten_list_of_dicts(items, section):
        result = []
        for item in items:
            if isinstance(item, dict):
                title = (item.get("title") or "").strip()
                dates = (item.get("dates") or "").strip()
                description = (item.get("description") or "").strip()

                if section == "professional_experience":
                    header = f"{title} ({dates})" if title and dates else title or dates
                    full_text = f"{header}\n{description}" if header else description
                    result.append(full_text.strip())

                elif section == "education":
                    degree = (item.get("degree") or "").strip()
                    institution = (item.get("institution") or "").strip()
                    dates = (item.get("dates") or "").strip()
                    edu_line = f"{degree} at {institution} ({dates})".strip(" ()")
                    result.append(edu_line)

                elif section == "certification_&_specialized_training":
                    name = (item.get("name") or "").strip()
                    date = (item.get("date") or "").strip()
                    cert_line = f"{name} ({date})" if name and date else name or date
                    result.append(cert_line)

                else:
                    parts = [f"{k.capitalize()}: {v}" for k, v in item.items() if v]
                    result.append("; ".join(parts))

        return "\n\n".join(result)

    def flatten_list_of_strings(items):
        return ", ".join(items)

    table_data = []
    if isinstance(parsed_results, dict):
        for label, key in [
            ('Name', 'name'),
            ('Professional Summary', 'professional_summary'),
            ('Professional Experience', 'professional_experience'),
            ('Education', 'education'),
            ('Certification & Specialized Training', 'certification_&_specialized_training'),
            ('Skills', 'skills'),
        ]:
            value = parsed_results.get(key, '')
            if isinstance(value, list):
                if value and isinstance(value[0], dict):
                    value = flatten_list_of_dicts(value, key)
                elif value and isinstance(value[0], str):
                    value = flatten_list_of_strings(value)
                else:
                    value = ""
            elif not isinstance(value, str):
                value = str(value)

            table_data.append({'label': label, 'value': value})

    context = {
        'llm_results': processing_results,
        'docx_path': docx_path,
        'table_data': table_data,
    }

    return render(request, 'upload_success.html', context)

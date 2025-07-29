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
                json_path,
            ) = llm_utils.process_pdf(uploaded_file)

            request.session['llm_processing_results'] = llm_text
            request.session['generated_docx'] = docx_path
            request.session['parsed_results'] = parsed_data
            request.session['json_path'] = json_path

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
    json_path = request.session.pop('json_path', None)

    # Define only the remaining fields for display
    sections = [
        ('Name', 'name'),
        ('Professional Summary', 'professional_summary'),
        ('Professional Experience', 'professional_experience'),
        ('Education', 'education'),
        ('Certification & Specialized Training', 'certification_&_specialized_training'),
        ('Skills', 'skills'),
    ]

    table_data = []
    if isinstance(parsed_results, dict):
        for label, key in sections:
            table_data.append({'label': label, 'value': parsed_results.get(key, '')})

    context = {
        'llm_results': processing_results,
        'docx_path': docx_path,
        'json_path': json_path,
        'table_data': table_data,
    }

    return render(request, 'upload_success.html', context)

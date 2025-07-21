from django.shortcuts import render, redirect

# Import llm_utils explicitly from the project package. Using an absolute
# import avoids accidentally pulling in a similarly named third-party
# module and ensures the expected functions are available.
# Import llm_utils from the parent package to avoid confusion with the
# Django project package that shares the same name. Using a relative
# import ensures Python loads the intended module.

import llm_utils

def uploadpage(request):
    if request.method == 'POST':
        # Access the uploaded file from the form field 'resume_file'
        if 'resume_file' in request.FILES:
            uploaded_file = request.FILES['resume_file']

            # Process the uploaded file using llm_utils
            # ``process_pdf`` returns the raw LLM text, the path to the
            # generated DOCX and JSON files, and the parsed data dictionary.
            (
                llm_text,
                docx_path,
                parsed_data,
                json_path,
            ) = llm_utils.process_pdf(uploaded_file)

            # Store the results, parsed data and path in the session
            request.session['llm_processing_results'] = llm_text
            request.session['generated_docx'] = docx_path
            request.session['parsed_results'] = parsed_data
            request.session['json_path'] = json_path

            print("File upload handled and processed")
            return redirect('/uploadsuccess/') # Redirect to the success page URL path
        else:
            # Handle case where no file was uploaded or input name is different
            print("No file uploaded or incorrect input name")
            return render(request, 'upload.html', {'error': 'Please upload a PDF file.'})

    return render(request, 'upload.html')

def uploadsuccess(request):
    # Retrieve the LLM processing results, parsed data and generated file path
    processing_results = request.session.pop('llm_processing_results', None)
    docx_path = request.session.pop('generated_docx', None)
    parsed_results = request.session.pop('parsed_results', None)
    json_path = request.session.pop('json_path', None)

    # Build table data for template rendering
    sections = [
        ('Name', 'name'),
        ('Address', 'address'),
        ('Phone Number', 'phone_number'),
        ('Email', 'email'),
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

    # Create a context dictionary
    context = {
        'llm_results': processing_results,
        'docx_path': docx_path,
        'json_path': json_path,
        'table_data': table_data,
    }

    # Render the success template with the results
    return render(request, 'upload_success.html', context)


# Use Python base image
FROM python:3.11-slim

# Prevent .pyc files and buffer
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set working directory
WORKDIR /app

# Copy requirement file and install dependencies
COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy all project files
COPY . /app/

# Collect static files
RUN python manage.py collectstatic --noinput

# Expose port
EXPOSE 8000

# Start app using Gunicorn
CMD ["gunicorn", "tool.wsgi:application", "--bind", "0.0.0.0:8000"]
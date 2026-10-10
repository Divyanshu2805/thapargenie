# The API with its locked requirements; the code itself is mounted from Backend/backend.
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --require-hashes -r /tmp/requirements.txt
WORKDIR /app
EXPOSE 8000
CMD ["gunicorn", "-c", "gunicorn.conf.py", "lt_wsgi"]

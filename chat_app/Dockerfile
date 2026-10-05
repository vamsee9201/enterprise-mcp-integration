FROM python:3.13-slim
WORKDIR /workspace
COPY chat_app/requirements.txt chat_app/requirements.txt
RUN pip install --no-cache-dir -r chat_app/requirements.txt
COPY backend backend
COPY chat_app chat_app
RUN useradd --uid 10001 --create-home chat
USER chat
EXPOSE 8080
CMD ["uvicorn", "chat_app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]

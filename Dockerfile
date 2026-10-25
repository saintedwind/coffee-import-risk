FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd --create-home appuser
USER appuser
EXPOSE 8501
CMD ["python", "-m", "streamlit", "run", "app.py", "--server.address=0.0.0.0"]


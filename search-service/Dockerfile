FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8003
CMD ["gunicorn", "search_service.wsgi:application", "--bind", "0.0.0.0:8003"]
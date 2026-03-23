FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt requirements.lock* ./
RUN pip install --no-cache-dir -r $([ -f requirements.lock ] && echo requirements.lock || echo requirements.txt)

COPY . .
RUN chmod +x entrypoint.sh

RUN adduser --disabled-password --no-create-home --gecos "" appuser
USER appuser

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM python:3.12-slim

WORKDIR /app

# Copy & install deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project (template already prepared with placeholders)
COPY . .

# Expose HF expected port
ENV PORT=7860
EXPOSE 7860

CMD python web/app.py

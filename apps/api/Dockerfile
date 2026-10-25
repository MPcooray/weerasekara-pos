FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY apps/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY apps/api .
RUN chmod +x /app/entrypoint.sh
RUN addgroup --system tetrova && adduser --system --ingroup tetrova tetrova \
    && chown -R tetrova:tetrova /app
USER tetrova
EXPOSE 8000
CMD ["/app/entrypoint.sh"]


FROM python:3.12-slim
WORKDIR /sandbox
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && rm -rf /root/.cache
COPY extractor.py ./extractor.py
RUN useradd --create-home --uid 10001 sandbox && chown -R sandbox:sandbox /sandbox
USER sandbox
ENTRYPOINT ["python", "/sandbox/extractor.py"]

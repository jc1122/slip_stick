FROM python:3.14.4-slim

WORKDIR /work
COPY . /work

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt

CMD ["python", "scripts/verify_publication_outputs.py"]

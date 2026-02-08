FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# scikit-learn wheels may require libgomp1.
# git is optional but helps /version build info when .git is available.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 git \
    && rm -rf /var/lib/apt/lists/*

# ---- deps layer ----
COPY requirements.txt pyproject.toml README.md ./
COPY src ./src

RUN python -m pip install -U pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir .

# ---- runtime files ----
COPY apps ./apps

EXPOSE 8000 8501

CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

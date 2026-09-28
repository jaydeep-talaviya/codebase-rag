FROM python:3.12-slim

# `git` is not optional here: app/services/repository.py shells out to
# `git clone` when a repository is submitted, so without this the first
# connection fails at request time with FileNotFoundError rather than at build.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /code

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Copied on its own so the dependency layer is cached until requirements change.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# alembic/ and alembic.ini ship because the schema is migrated, never created
# at startup: nothing in app/ calls create_all, so an un-migrated database
# fails on the first query instead of on boot.
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini

# Clones land in /code/data/repositories. Created up front (owned by the
# runtime user) because the target's parent has to exist before git clone runs.
RUN mkdir -p /code/data/repositories \
    && useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /code

# The CrossEncoder in app/services/reranker.py is downloaded on first use; give
# it a writable cache so it does not need a writable $HOME to be useful.
ENV HF_HOME=/code/.cache/huggingface

USER appuser
EXPOSE 8000

# Migrations run before the server, and a failure is fatal on purpose: serving
# traffic against a schema that does not match the code fails later and more
# confusingly than refusing to start. compose waits for postgres to be healthy
# first, so this does not race the database.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]

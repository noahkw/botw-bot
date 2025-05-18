FROM python:3.12-bullseye

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# fix for Git's new 'detected dubious ownership in repository at '/app''
RUN git config --global --add safe.directory '*'

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libffi-dev \
    libnacl-dev \
    libsodium-dev

COPY pyproject.toml ./
RUN pip install uv && uv sync

CMD ["uv", "run", "launcher.py"]

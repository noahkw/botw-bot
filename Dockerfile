FROM gorialis/discord.py:3.9-slim-buster-master-minimal

WORKDIR /app

COPY pyproject.toml poetry.lock ./
RUN pip install poetry && poetry config virtualenvs.create false && poetry install

CMD ["python", "launcher.py"]

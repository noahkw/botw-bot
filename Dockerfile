FROM gorialis/discord.py:3.8.1-slim-buster-master-minimal

WORKDIR /app

COPY requirements.txt ./
RUN poetry install

CMD ["python", "launcher.py"]

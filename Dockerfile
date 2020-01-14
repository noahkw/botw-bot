FROM gorialis/discord.py:3.7.4-buster-master-minimal

WORKDIR /app

COPY requirements.txt ./
RUN pip install -r requirements.txt

CMD ["python", "botw-bot.py"]
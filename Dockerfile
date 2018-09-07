FROM python:3
RUN pip3 install matrix-bot-api
COPY pollbot/pollbot.py ./pollbot.py
COPY config.ini ./config.ini
CMD [ "python3", "pollbot.py" ]
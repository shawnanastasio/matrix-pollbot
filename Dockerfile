FROM python:3
RUN pip3 install matrix-bot-api
ADD pollbot/pollbot.py ./pollbot.py
ADD config.ini ./config.ini
ENTRYPOINT [ "python3", "pollbot.py" ]
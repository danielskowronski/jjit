FROM python:3.11.0b4-slim-bullseye

ENV TELEGRAM_TOKEN=123456:FsadfsdafWGsDFbvFDSKAEfldsafKGFAG
ENV TELEGRAM_CHAT=123456789
ENV JJIT_PARAMS="--category devops admin support architecture other security --fully_remote --salary 22000 --dont-send --state-file /jjit_cache/jjit.txt"

COPY requirements.txt requirements.txt
COPY jjit.py /jjit.py

RUN \
    echo "[telegram]"                   > /etc/telegram-send.conf; \
    echo "token   = ${TELEGRAM_TOKEN}" >> /etc/telegram-send.conf; \
    echo "chat_id = ${TELEGRAM_CHAT}"  >> /etc/telegram-send.conf;

RUN python3 -m pip install -r requirements.txt

CMD python3 /jjit.py ${JJIT_PARAMS}

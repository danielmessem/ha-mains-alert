ARG BUILD_FROM
FROM $BUILD_FROM

RUN apk add --no-cache python3 py3-pip \
    && python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir Flask==3.1.2 requests==2.32.5

COPY app.py detector.py index.html run.sh /
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]


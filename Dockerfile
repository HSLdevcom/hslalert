FROM python:2
MAINTAINER Reittiopas version: 0.1

ENV WORK=/opt/hslalert

WORKDIR ${WORK}

# Add application
RUN mkdir -p ${WORK}
ADD . ${WORK}
RUN pip install -r requirements.txt

EXPOSE 5000

CMD export TZ="Europe/Helsinki" && python app.py

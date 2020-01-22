FROM python:3.7-slim
RUN apt-get update && apt-get install -y zip

ENV APP_HOME /app
WORKDIR $APP_HOME

COPY requirements.txt ./
# grpc separate as python won't load .so's from a zip
RUN mkdir imports \
 && pip install -r requirements.txt -t imports \
 && cd imports \
 && mv grpc .. \
 && zip -r ../imports.zip * \
 && cd .. \
 && rm -rf imports \
 && rm requirements.txt
COPY static/* static/
COPY data/* data/
COPY *.py ./

CMD PYTHONPATH=imports.zip exec python3 -m gunicorn.app.wsgiapp --bind :$PORT --workers 3 --threads 8 app:app

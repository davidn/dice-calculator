#!/usr/bin/env python

import os

from flask import Flask, request, send_from_directory
from main import handleHttp

app = Flask(__name__)
@app.route('/v1', methods=["POST"])
@app.route('/', methods=["POST"])  # alias for the lazy
@app.route('/roll', methods=["POST"])  # compatibility with cloud func
def entry():
    return handleHttp(request)


@app.route('/v1/openapi.yaml')
def openapi():
    return send_from_directory('static', 'openapi.yaml')


@app.route('/v1/dialogflow.yaml')
def dialogflow_openapi():
    return send_from_directory('static', 'dialogflow.yaml')


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

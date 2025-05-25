import sys
import flask
import os
import json

from flask import send_file, abort
from waitress import serve

app = flask.Flask(__name__)

IMAGE_FILENAME = 'screenshot.jpg'  # Change to your image filename
PATH = sys.path[0] + "/"


with open(os.path.join(PATH, 'config.json')) as f:
    config = json.load(f)

@app.route('/')
def serve_image():
    if os.path.exists(IMAGE_FILENAME):
        return send_file(IMAGE_FILENAME, mimetype='image/jpeg')
    else:
        abort(404)

def run_server():
    print('Server initialized')
    print('Server running on http://localhost:' + str(config['SERVER_Port']))
    serve(app, host='0.0.0.0', port=config['SERVER_Port'])
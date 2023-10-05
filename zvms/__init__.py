from flask import Flask, redirect, send_file, make_response
from flask_cors import CORS

from .toolkit import Toolkit
from .views import Views
from .api import Api
from .misc import db
from . import config

app = Flask(__name__)
app.config.from_object(config)
CORS(app, supports_credentials={'/api/*'})

db.init_app(app)


@app.route('/')
def index():
    return redirect('/user/login')


@app.route('/favicon.ico')
def favicon():
    return send_file('favicon.ico')


app.register_blueprint(Api)
app.register_blueprint(Views)
app.register_blueprint(Toolkit)

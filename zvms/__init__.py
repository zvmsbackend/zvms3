from flask import Flask, redirect, send_file
from flask_cors import CORS

from .management import Management
from .volunteer import Volunteer
from .thought import Thought
from .toolkit import Toolkit
from .about import About
from .admin import Admin
from .user import User
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
app.register_blueprint(User)
app.register_blueprint(About)
app.register_blueprint(Admin)
app.register_blueprint(Thought)
app.register_blueprint(Toolkit)
app.register_blueprint(Volunteer)
app.register_blueprint(Management)

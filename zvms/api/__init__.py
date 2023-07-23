from flask import Blueprint

from .user import User
from .admin import Admin
from .issue import Issue
from .notice import Notice
from .thought import Thought
from .volunteer import Volunteer

Api = Blueprint('Api', __name__, url_prefix='/api')

Api.register_blueprint(User)
Api.register_blueprint(Admin)
Api.register_blueprint(Issue)
Api.register_blueprint(Notice)
Api.register_blueprint(Thought)
Api.register_blueprint(Volunteer)

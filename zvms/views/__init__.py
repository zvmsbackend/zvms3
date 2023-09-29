from flask import Blueprint

from .about import About
from .admin import Admin
from .management import Management
from .thought import Thought
from .user import User
from .volunteer import Volunteer

Views = Blueprint('Views', __name__)

Views.register_blueprint(About)
Views.register_blueprint(Admin)
Views.register_blueprint(Management)
Views.register_blueprint(Thought)
Views.register_blueprint(User)
Views.register_blueprint(Volunteer)

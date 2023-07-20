import json

from flask import Blueprint
import requests

from .dict import Dict
from ..framework import (
    toolkit_view
)
from ..util import render_template

Toolkit = Blueprint('Toolkit', __name__, url_prefix='/toolkit')

Toolkit.register_blueprint(Dict)

@Toolkit.route('/')
@toolkit_view
def index():
    return render_template('toolkit/index.html')

@Toolkit.route('/wallpapers')
@toolkit_view
def wallpapers():
    res = requests.get('https://bing.com/HPImageArchive.aspx?format=js&idx=0&n=7')
    data = json.loads(res.text)['images']
    return render_template(
        'toolkit/wallpapers.html',
        imgs=[
            (i, {
                'url': 'https://bing.com' + img['url'],
                'title': img['title'],
                'copyright': img['copyright']
            }) for i, img in enumerate(data)
        ]
    )
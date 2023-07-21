from datetime import date, datetime
import json
import re

from flask import (
    Blueprint,
    redirect,
    session
)
import requests

from .dict import Dict
from ..framework import (
    login_required,
    toolkit_view,
    route,
    url
)
from ..util import (
    render_template,
    execute_sql,
    random_color
)

Toolkit = Blueprint('Toolkit', __name__, url_prefix='/toolkit')

Toolkit.register_blueprint(Dict)


@Toolkit.route('/')
@toolkit_view
def index():
    return render_template('toolkit/index.html')


@Toolkit.route('/wallpapers')
@toolkit_view
def wallpapers():
    res = requests.get(
        'https://bing.com/HPImageArchive.aspx?format=js&idx=0&n=7')
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


@Toolkit.route('/birthday')
@toolkit_view
def birthday_get():
    today = date.today()
    birthday_today = execute_sql(
        'SELECT userid, username '
        'FROM user '
        'WHERE userid IN '
        '(SELECT userid '
        'FROM birthday '
        'WHERE month = :month AND day = :day)',
        month=today.month,
        day=today.day
    ).fetchall()
    birthday_thismonth = execute_sql(
        'SELECT b.userid, user.username, b.day '
        'FROM birthday AS b '
        'JOIN user ON user.userid = b.userid '
        'WHERE b.month = :month '
        'ORDER BY b.day',
        month=today.month
    )
    profile = None
    if 'userid' in session:
        match execute_sql(
            'SELECT year, month, day '
            'FROM birthday '
            'WHERE userid = :userid',
            userid=session.get('userid')
        ).fetchone():
            case None: ...
            case spam:
                profile = (session.get('username'), *spam)
    return render_template(
        'toolkit/birthday.html',
        today=birthday_today,
        thismonth=birthday_thismonth,
        profile=profile,
        month=today.month,
        random_color=random_color
    )


@route(Toolkit, url.birthday)
@login_required
@toolkit_view
def birthday(birthday: date):
    match execute_sql(
        'SELECT COUNT(*) FROM birthday WHERE userid = :userid',
        userid=session.get('userid')
    ).fetchone():
        case [0]: ...
        case _:
            return render_template('toolkit/error.html', msg='生日已注册')
    execute_sql(
        'INSERT INTO birthday(userid, year, month, day) '
        'VALUES(:userid, :year, :month, :day)',
        userid=session.get('userid'),
        year=birthday.year,
        month=birthday.month,
        day=birthday.day
    )
    return redirect('/toolkit/birthday')


@Toolkit.route('/3500')
@toolkit_view
def words_3500():
    return render_template('toolkit/3500.html')


@Toolkit.route('/weather')
@toolkit_view
def msn_weather():
    res = requests.get('https://www.msn.cn/zh-cn/weather/forecast/')
    match = re.search(
        r'\<script id="redux-data" type="application/json"\>([\s\S]+?)\</script\>', res.text)
    data = json.loads(match.group(1))
    return render_template(
        'toolkit/weather.html',
        **data['WeatherData']['_@STATE@_'],
        enumerate=enumerate,
        zip=zip,
        datetime=datetime,
        location=data['WeatherPageMeta']['_@STATE@_']['location']['displayName'],
        chart_data=json.dumps([
            (i['dayTextLocaleString'], i['highTemperature'], i['lowTemperature'])
            for i in data['WeatherData']['_@STATE@_']['forecast']
        ], ensure_ascii=False)
    )

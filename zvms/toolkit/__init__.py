from operator import itemgetter
import os.path
import sqlite3
import json
import csv

from flask import (
    Blueprint,
    redirect,
    request,
    abort
)

from ..framework import (
    ZvmsError,
    lengthedstr,
    login_required,
    permission,
    toolkit_route,
    url
)
from ..util import (
    get_with_timeout,
    render_template
)
from ..misc import Permission, logger

Toolkit = Blueprint('Toolkit', __name__, url_prefix='/toolkit')

directory, _ = os.path.split(__file__)
try:
    with open(os.path.join(directory, 'weather-api-key'), encoding='utf-8') as f:
        WEATHER_API_KEY = f.read()
except OSError:
    logger.warning(
        '`weather-api-key` not found. Weather forecast service will not be provided.')
    WEATHER_API_KEY = None

try:
    with open(os.path.join(directory, 'ecdict.csv'), encoding='utf-8') as f:
        sql = '''
                CREATE TABLE stardict(
                `word` VARCHAR(64) NOT NULL PRIMARY KEY,
                `phonetic` VARCHAR(64),
                `definition` TEXT,
                `translation` TEXT
                )
                '''
        connection = sqlite3.connect(':memory:')
        cursor = connection.cursor()
        cursor.execute(sql)
        reader = iter(csv.reader(f))
        next(reader)
        for word, phonetic, definition, translation, *_ in reader:
            cursor.execute(
                'INSERT INTO stardict(`word`, `phonetic`, `definition`, `translation`) VALUES(?, ?, ?, ?)',
                (word, phonetic, definition, translation)
            )
except OSError:
    logger.warning(
        '`ecdict.csv` not found. Online dictionary service will not be provided.')
    cursor = None

try:
    with open(os.path.join(directory, 'toolkit-settings.json'), encoding='utf-8') as f:
        settings = json.load(f)
except OSError:
    logger.info(
        '`toolkit-settings.json` not found. Default settings have been applied.')
    settings = {
        'libraryUrl': '',
        'music': None,
        'opening': {
            'kind': 'close'
        }
    }


@toolkit_route(Toolkit, url(''), 'GET')
def index():
    return render_template('toolkit/index.html')


@toolkit_route(Toolkit, url.wallpapers, 'GET')
def wallpapers():
    res = get_with_timeout(
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


_no_word = object()


@toolkit_route(Toolkit, url.dict, 'GET')
def dict_get(
    kind: str = _no_word,
    word: lengthedstr[45] = _no_word
):
    if cursor is None:
        raise ZvmsError('电子词典不可用')
    if word is _no_word:
        return render_template('toolkit/dict_query.html')
    if kind not in ('e2c', 'c2e', 'indeterminate'):
        abort(404)
    match kind:
        case 'e2c':
            clause = 'word = ?'
        case 'c2e':
            clause = 'translation LIKE ?'
            word = f'%{word}%'
        case 'indeterminate':
            clause = 'word LIKE ?'
            word = f'%{word}%'
    sql = 'SELECT word, phonetic, definition, translation FROM stardict WHERE ' + clause
    cursor.execute(sql, (word,))
    match cursor.fetchall():
        case None:
            raise ZvmsError('查无此结果')
        case [[word, phonetic, definition, translation]]:
            return render_template(
                'toolkit/dict_result.html',
                word=word,
                phonetic=phonetic,
                definition=definition.split('\\n'),
                translation=translation.split('\\n')
            )
        case results:
            return render_template('toolkit/dict_results.html', results=map(itemgetter(0), results))


@toolkit_route(Toolkit, url('3500'), 'GET')
def words_3500():
    return render_template('toolkit/3500.html')


@toolkit_route(Toolkit, url.weather, 'GET')
def weather():
    if WEATHER_API_KEY is None:
        raise ZvmsError('天气预报不可用')
    LOCATION = '121.714351,29.952756'
    weather24h = get_with_timeout(
        f'https://devapi.qweather.com/v7/grid-weather/24h?key={WEATHER_API_KEY}&location={LOCATION}')
    weather7d = get_with_timeout(
        f'https://devapi.qweather.com/v7/grid-weather/7d?key={WEATHER_API_KEY}&location={LOCATION}')
    return render_template(
        'toolkit/weather.html',
        weather24h=weather24h.text,
        weather7d=weather7d.text
    )


@toolkit_route(Toolkit, url.literacy, 'GET')
def literacy():
    return render_template(
        'toolkit/literacy.html',
        library_url=settings['libraryUrl'],
        music=settings['music']
    )


@toolkit_route(Toolkit, url.management, 'GET')
@login_required
@permission(Permission.ADMIN)
def management_get():
    return render_template(
        'toolkit/management.html',
        library_url=settings['libraryUrl']
    )


def save_settings():
    with open(os.path.join(directory, 'toolkit-settings.json'), 'w', encoding='utf-8') as f:
        json.dump(settings, f)


@toolkit_route(Toolkit, url.management, 'POST')
@login_required
@permission(Permission.ADMIN)
def management_post():
    match request.form:
        case {'action': 'set-library-url', 'url': url}:
            settings['libraryUrl'] = url
        case {'action': 'search-music', 'keyword': keyword}:
            data = json.loads(
                get_with_timeout(
                    f'https://tonzhon.com/api/fuzzy_search?keyword={keyword}'
                ).text
            )['songs']
            for datum in data:
                datum['url'] = json.loads(get_with_timeout('https://music-api.tonzhon.com/song_file/' + datum['newId']).text)['data']
            return render_template('toolkit/music_search.html', data=data)
        case {'action': 'close-music'}:
            settings['music'] = None
        case {'action': 'set-opening', 'kind': 'timeLimit', 'start': start, 'end': end}:
            settings['opening'] = {
                'kind': 'timeLimit',
                'start': start,
                'end': end
            }
        case {'action': 'set-opening', 'kind': kind}:
            settings['opening']['kind'] = kind
        case _:
            return render_template('toolkit/error.html', msg='无效的管理动作: ' + json.dumps(request.form))
    save_settings()
    return redirect('/toolkit/management')


@toolkit_route(Toolkit, url.music_search, 'POST')
@login_required
@permission(Permission.ADMIN)
def music_search(title: str, url: str):
    settings['music'] = {
        'title': title,
        'url': url
    }
    save_settings()
    return redirect('/toolkit/management')


@Toolkit.route('/heartbeat')
def heartbeat():
    return json.dumps(settings['opening'])

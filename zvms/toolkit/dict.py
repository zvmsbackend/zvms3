from urllib.parse import quote

from flask import (
    Blueprint,
    abort
)
from bs4.element import Tag
import requests
import bs4

from ..framework import (
    lengthedstr,
    toolkit_view,
    route,
    url
)
from ..util import render_template

Dict = Blueprint('Dict', __name__, url_prefix='/dict')

_no_word = object()

def bing_dict_helper(soup: bs4.BeautifulSoup, div_id: str) -> map:
    div = soup.find('div', id=div_id)
    if div is None:
        return ()
    return map(Tag.get_text, div.find_all('tr', class_='def_row'))

def zh_dict_helper(soup: bs4.BeautifulSoup, cls: str, tagname: str) -> map:
    tag = soup.find('div', class_=cls)
    if tag is None:
        return ()
    return map(Tag.get_text, tag.find_all(tagname))

@route(Dict, url['kind', 'str'], 'GET', 'toolkit/error.html')
@toolkit_view
def bing_dictionary_get(
    kind: str,
    word: lengthedstr[45] = _no_word
):
    if kind not in ('bing', 'zh'):
        abort(404)
    prompt = {
        'bing': '单词',
        'zh': '词语'
    }[kind]
    if word is _no_word:
        return render_template(
            'toolkit/dict/query.html',
            prompt=prompt
        )
    word = word.strip().lower()
    if not word:
        return render_template('toolkit/error.html', msg=prompt + '不可为空')
    if kind == 'bing':
        res = requests.get('https://cn.bing.com/dict?q=' + quote(word))
        soup = bs4.BeautifulSoup(res.text, 'lxml')
        pronunciation = soup.find('div', {'class': 'hd_p1_1'}).get_text()
        return render_template(
            'toolkit/dict/result.html',
            body=pronunciation,
            word=word,
            data=list(enumerate(
                (title, id, bing_dict_helper(soup, id))
                for title, id in (('英汉释义', 'crossid'), ('英英/汉汉释义', 'homoid'), ('网络释义', 'webid'))
            )),
            examples_link='/toolkit/dict/bing/examples?word=' + quote(word)
        )
    res = requests.get('https://www.zdic.net/hans/' + quote(word))
    if not res.text:
        return render_template('toolkit/error.html', msg='查无此结果')
    soup = bs4.BeautifulSoup(res.text, 'lxml')
    if res.url.startswith('https://www.zdic.net/e/sci/index.php'):
        if soup.find('li') is None:
            return render_template('toolkit/error.html', msg='查无此结果')
        items = [
            i.get_text().rstrip(i.find('span').string)
            for i in soup.find('div', class_='sslist').find_all('a')
        ]
        return render_template(
            'toolkit/dict/zh_search.html',
            items=items
        )
    elif len(word) == 1:
        return render_template(
            'toolkit/dict/result.html',
            word=word,
            data=list(enumerate(
                (title, cls, zh_dict_helper(soup, cls, tagname))
                for title, cls, tagname in (
                    ('基本解释', 'jbjs', 'li'), 
                    ('详细解释', 'xxjs', 'p'), 
                    ('康熙字典', 'kxzd', 'p'), 
                    ('说文解字', 'swjz', 'p')
                )
            ))
        )
    return render_template(
        'toolkit/dict/result.html',
        word=word,
        data=list(enumerate(
            (title, cls, zh_dict_helper(soup, cls, 'li'))
            for title, cls in (('词语解释', 'jbjs'), ('网络解释', 'wljs'))
        ))
    )
    
@route(Dict, url.bing.examples, 'GET', 'toolkit/error.html')
@toolkit_view
def bing_examples(
    word: str,
    page: int = 1
):
    res = requests.get('https://bing.com/dict/service?q={}&offset={}&dtype=sen&&qs=n'.format(
        word,
        page * 10 - 10
    ))
    soup = bs4.BeautifulSoup(res.text, 'lxml')
    pages = soup.find('div', class_='b_pag')
    if pages is None:
        return render_template('toolkit/error.html', msg='无相关结果')
    pages = list(map(Tag.get_text, pages.find_all('a', class_='b_primtxt')))
    sentences = [
        [
            tag.find('div', class_=cls).get_text()
            for cls in ('sen_en', 'sen_cn', 'sen_li')
        ]
        for tag in soup.find_all('div', class_='se_li')
    ]
    return render_template(
        'toolkit/dict/examples.html',
        sentences=sentences,
        pages=pages,
        word=word,
        page=page
    )
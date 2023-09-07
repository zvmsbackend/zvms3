from urllib.parse import quote

from flask import (
    Blueprint,
    abort
)
from bs4.element import Tag
import bs4

from ..framework import (
    ZvmsError,
    lengthedstr,
    toolkit_route,
    url
)
from ..util import render_template, get_with_timeout

Dict = Blueprint('Dict', __name__, url_prefix='/dict')

_no_word = object()


def bing_dict_helper(soup: bs4.BeautifulSoup, div_id: str) -> map:
    div = soup.find('div', id=div_id)
    if div is None:
        return ()
    return map(Tag.get_text, div.find_all('tr', class_='def_row'))


def zh_dict_helper(soup: bs4.BeautifulSoup, cls: str, tagname: str) -> map:
    div = soup.find('div', class_=cls)
    if div is None:
        return ()
    return map(Tag.get_text, div.find_all(tagname))


@toolkit_route(Dict, url['kind', 'string'], 'GET')
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
        raise ZvmsError(prompt + '不可为空')
    if kind == 'bing':
        res = get_with_timeout('https://cn.bing.com/dict?q=' + quote(word))
        soup = bs4.BeautifulSoup(res.text, 'lxml')
        if soup.find('div', class_='no_results') is not None:
            raise ZvmsError('查无此结果')
        pronunciation = soup.find('div', {'class': 'hd_p1_1'}).get_text()
        return render_template(
            'toolkit/dict/result.html',
            text=pronunciation,
            word=word,
            data=list(enumerate(
                (title, id, bing_dict_helper(soup, id))
                for title, id in (('英汉释义', 'crossid'), ('英英/汉汉释义', 'homoid'), ('网络释义', 'webid'))
            )),
            examples_link='/toolkit/dict/bing/examples?word=' + quote(word)
        )
    res = get_with_timeout('https://www.zdic.net/hans/' + quote(word))
    if not res.text:
        raise ZvmsError('查无此结果')
    soup = bs4.BeautifulSoup(res.text, 'lxml')
    if res.url.startswith('https://www.zdic.net/e/sci/index.php'):
        if soup.find('li') is None:
            raise ZvmsError('查无此结果')
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


@toolkit_route(Dict, url.bing.examples, 'GET')
def bing_examples(
    word: str,
    page: int = 1
):
    res = get_with_timeout(
        f'https://bing.com/dict/service?q={word}&offset={page * 10 - 10}&dtype=sen&&qs=n')
    soup = bs4.BeautifulSoup(res.text, 'lxml')
    pages = soup.find('div', class_='b_pag')
    if pages is None:
        raise ZvmsError('无相关结果')
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

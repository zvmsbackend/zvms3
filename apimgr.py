from typing import (
    TypedDict, 
    GenericAlias,
    is_typeddict,
    _LiteralGenericAlias 
)
from operator import attrgetter
from time import perf_counter
from itertools import chain
from enum import EnumType
from datetime import date
import argparse
import os.path
import shutil
import json
import re

start = perf_counter()

from flask import render_template as _render_template

from zvms.framework import (
    _ListValidatorMaker,
    _StringValidatorMaker, 
    Api
)
from zvms.util import render_markdown
from zvms.api import Api as ApiBlueprint
from zvms import misc, app


def write_file(filename: str, *content) -> None:
    with open(filename, 'w', encoding='utf-8') as file:
        file.write(str.join('', content))
    print(os.path.realpath(filename), '生成完成')


def snake2camel(snake: str) -> str:
    split = snake.split('_')
    return split[0] + ''.join(map(str.title, split[1:]))


def snake2pascal(snake: str) -> str:
    return ''.join(map(str.title, snake.split('_')))


def pascal2camel(pascal: str) -> str:
    return pascal[0].lower() + pascal[1:]


enums = {
    cls for cls in misc.__dict__.values() 
    if isinstance(cls, type) and issubclass(cls, misc.ZvmsEnum) and cls is not misc.ZvmsEnum
} 


def dump_enum(dst: str) -> None:
    def format_fields(cls) -> str:
        return',\n'.join(
            f'    {snake2pascal(name)} = {value.value}'
            for name, value in cls._member_map_.items()
        )
    
    write_file(dst, '\n'.join(
        """export enum {pascal_name} {{
{fields}
}};
const {camel_name}ToString = [
{tostring}
];
""".format(
            pascal_name=cls.__name__,
            camel_name=pascal2camel(cls.__name__),
            fields=format_fields(cls),
            tostring=',\n'.join(f"    '{i}'" for i in cls.__tostr__)
        )
        for cls in enums
    ), """
export enum Permission {{
{fields}
}};
const permissionToString = {{
{map_fields}
}};

""".format(
        fields=format_fields(misc.Permission),
        map_fields=',\n'.join(
            f"    [Permission.{snake2pascal(name)}]: '{misc.permission2str[value]}'"
            for name, value in misc.Permission._member_map_.items()
        )
), """export {{
{exports} 
}};""".format(
        exports=',\n'.join(
            f'    {clsname}ToString'
            for clsname in chain(map(attrgetter('__name__'), enums), ('permission',))
        )
))
    

def search_structs() -> list[TypedDict]:
    ret = set()
    def search(t: type) -> None:
        if is_typeddict(t):
            ret.add(t)
            for v in t.__annotations__.values():
                search(v)
        elif isinstance(t, GenericAlias):
            search(*t.__args__)
        elif isinstance(t, _ListValidatorMaker):
            search(t.generic_argument)

    for api in Api.apis:
        for param in api.params.values():
            search(param)
        search(api.returns)
    return sorted(ret, key=attrgetter('__name__'))
    

structs = search_structs()


def py2ts(ann: type, in_structs: bool, enable_link: bool = False) -> str:
    if is_typeddict(ann):
        if enable_link:
            return f'<a href="/structs.html#{ann.__name__}">{ann.__name__}</a>'
        return ann.__name__ if in_structs else 'structs.' + ann.__name__
    match ann:
        case str():
            return ann
        case EnumType():
            if enable_link:
                return f'enums.<a href="/enums.html#{ann.__name__}">{ann.__name__}</a>'
            return 'enums.' + ann.__name__
        case GenericAlias(__args__=[arg]):
            return py2ts(arg, in_structs, enable_link) + '[]'
        case _ListValidatorMaker(generic_argument=arg):
            return py2ts(arg, in_structs, enable_link) + '[]'
        case _StringValidatorMaker():
            return 'string'
        case _LiteralGenericAlias(__args__=args):
            return ' | '.join(str(a.value) for a in args)
    return {
        bool: 'boolean',
        int: 'number',
        str: 'string',
        date: 'string',
        None: 'null'
    }[ann]


def dumps_struct(struct: TypedDict, enable_link: bool = False) -> str:
    return """export interface {name} {{
{fields}
}};
""".format(
        name=struct.__name__,
        fields=',\n'.join(
            f'    {name}: {py2ts(ann, True, enable_link)}'
            for name, ann in struct.__annotations__.items()
        )
    )


def dump_structs(dst: str) -> None:
    write_file(dst, 'import * as enum from "./enums";\n\n', '\n'.join(map(dumps_struct, structs)))
    

def dump_api(template_file: str, dst: str) -> None:
    with open(template_file, encoding='utf-8') as file:
        template = file.read()
    write_file(dst, re.sub(r'//--METHODS START----[\s\S]*//--METHODS END----', '\n'.join(
"""  /**
   * {doc}
   * ### [{method}] /api{url}
   * #### 权限: {permission}{comment_params}
   */
  {name}({params}): ForegroundApiRunner<{returns}> {{
    return createForegroundApiRunner({function_args});
  }}
""".format(
        doc=api.doc or '',
        method=api.method,
        url=api.blueprint.url_prefix + api.url.string,
        permission=api.permission,
        comment_params='' if not api.total_params else '\n' + '\n'.join(
            f'   * @param {name}'
            for name in api.total_params
        ),
        name=snake2camel(api.name),
        params='' if not api.total_params else '\n' + ',\n'.join(
            f'    {name}: {py2ts(ann, False)}'
            for name, ann in api.total_params.items()
        ) + '\n  ',
        returns=py2ts(api.returns, False),
        function_args=f'this, "{api.method}", `{backslash_url}`' if not api.params
        else """
      this,
      "{method}",
      `{backslash_url}`, {{
{params}
      }}
    """.format(
        method=api.method,
        backslash_url=backslash_url,
        params=',\n'.join(
            f'        {param}'
            for param in api.params
        )
)
)
for api in Api.apis
if (backslash_url := re.sub(r'<(int:)?(.+?)>', r'${\2}', api.url.string))
or True
    ), template))


_enums_names = list(map(attrgetter('__name__'), enums))
_structs_names = list(map(attrgetter('__name__'), structs))
blueprints = [b for b, _ in ApiBlueprint._blueprints]


def render_template(template_name: str, **context) -> str:
    return _render_template(
        template_name,
        enums=_enums_names,
        structs=_structs_names,
        blueprints=blueprints,
        **context
    )


def parse_sql(sql: str) -> list[tuple[str, dict[str, list[str]]]]:
    create_stmts = re.findall(r'CREATE TABLE.*\b(\w+)\(([\s\S]+?)\);', sql)
    ret = []
    for tab, body in create_stmts:
        rows = {}
        for line in map(str.strip, re.split(r',\s*?\n', body)):
            if (m := re.match(r'FOREIGN KEY\s*\((\w+)\)\s*REFERENCES\s*(\w+)\s*\((\w+)\)', line)) is not None:
                rows[m.group(1)][1].append(f'REFERENCES <a href="#{m.group(2)}">{m.group(2)}</a>({m.group(3)})')
            elif (m := re.match(r'PRIMARY KEY\s*\((.+)\)', line)) is not None:
                for i in re.split(r',\s*', m.group(1)):
                    rows[i][1].append('PRIMARY KEY')
            else:
                name, type, *props = line.split(maxsplit=2)
                rows[name] = [type, props]
        ret.append((tab, rows))
    return ret


def dump_document(dst: str) -> None:
    app.app_context().push()
    with open('zvms.sql', encoding='utf-8') as file:
        sql = file.read()
    if not os.path.exists(dst):
        os.mkdir(dst)
    if not os.path.exists(os.path.join(dst, 'static')):
        os.mkdir(os.path.join(dst, 'static'))
        for dir in ['js', 'css', 'img', 'font']:
            shutil.copytree(os.path.join('zvms', 'static', dir), os.path.join(dst, 'static', dir))
    shutil.copy(os.path.join('zvms', 'favicon.ico'), os.path.join(dst, 'favicon.ico'))
    write_file(os.path.join(dst, 'index.html'), render_template('document/index.html'))
    write_file(os.path.join(dst, 'notes.html'), render_template('document/notes.html'))
    write_file(os.path.join(dst, 'enums.html'), render_template(
        'document/enums.html',
        data=chain(
            ((enum.__name__, (
                (name, value, enum.__tostr__[value - 1])
                for name, value in enum._member_map_.items()
            ))
            for enum in enums),
            (('Permission',(
                (name, value, misc.permission2str[value])
                for name, value in misc.Permission._member_map_.items()
            )),)
        )
    ))
    write_file(os.path.join(dst, 'structs.html'), render_template(
        'document/structs.html',
        data=[
            (struct.__name__, dumps_struct(struct, True))
            for struct in structs
        ]
    ))
    write_file(os.path.join(dst, 'blueprints.html'), render_template(
        'document/blueprints.html',
        render_markdown=render_markdown,
        snake2camel=snake2camel,
        py2ts=py2ts,
        dict=dict
    ))
    write_file(os.path.join(dst, 'database.html'), render_template(
        'document/database.html',
        schema=parse_sql(sql)
    ))


def main() -> None:
    try:
        with open('apimgr.json', encoding='utf-8') as file:
            cfg = argparse.Namespace(**json.load(file))
    except OSError:
        parser = argparse.ArgumentParser()
        parser.add_argument('-e', '--enum', required=True, help='枚举.ts文件的输出路径')
        parser.add_argument('-s', '--struct', required=True, help='接口.ts文件的输出路径')
        parser.add_argument('-a', '--api', required=True, help='API.ts文件的输出路径')
        parser.add_argument('-t', '--api-template', required=True, help='API模板的路径')
        parser.add_argument('-d', '--doc', required=True, help='HTML文档的输出文件夹')
        cfg = parser.parse_args()
    dump_enum(cfg.enum)
    dump_api(cfg.api_template, cfg.api)
    dump_structs(cfg.struct)
    dump_document(cfg.doc)
    print('耗时', perf_counter() - start, '秒')


if __name__ == '__main__':
    main()

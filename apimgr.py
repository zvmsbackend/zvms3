from typing import (
    TypedDict, 
    GenericAlias,
    is_typeddict,
    _LiteralGenericAlias 
)
from operator import itemgetter
from time import perf_counter
from itertools import chain
from enum import EnumType
from datetime import date
import argparse
import os.path
import json
import re

start = perf_counter()

from zvms.framework import (
    _RequiredListValidatorMaker,
    _StringValidatorMaker, 
    Api
)
from zvms import misc


def write_file(filename: str, *content):
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


def dump_enum(dst: str) -> None:
    enums = [
        (name, cls)
        for name, cls in misc.__dict__.items()
        if isinstance(cls, type) and issubclass(cls, misc.ZvmsEnum) and cls is not misc.ZvmsEnum
    ]
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
            pascal_name=name,
            camel_name=pascal2camel(name),
            fields=format_fields(cls),
            tostring=',\n'.join(f"    '{i}'" for i in cls.__tostr__)
        )
        for name, cls in enums
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
            for clsname in chain(map(itemgetter(0), enums), ('permission',))
        )
))
    

def search_structs() -> set[TypedDict]:
    ret = set()
    def search(t: type) -> None:
        if is_typeddict(t):
            ret.add(t)
            for v in t.__annotations__.values():
                search(v)
        elif isinstance(t, GenericAlias):
            search(*t.__args__)

    for api in Api.apis:
        for param in api.params:
            search(param)
        search(api.returns)
    return ret


def py2ts(ann: type, in_structs: bool) -> str:
    if is_typeddict(ann):
        return ann.__name__ if in_structs else 'structs.' + ann.__name__
    match ann:
        case str():
            return ann
        case EnumType():
            return 'enums.' + ann.__name__
        case GenericAlias(__args__=[arg]):
            return py2ts(arg, in_structs) + '[]'
        case _RequiredListValidatorMaker(generic_argument=arg):
            return py2ts(arg, in_structs) + '[]'
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


def dump_structs(dst: str) -> None:
    structs = search_structs()
    write_file(dst, 'import * as enum from "./enums";\n\n', '\n'.join(
"""export interface {name} {{
{fields}
}};
""".format(
        name=struct.__name__,
        fields=',\n'.join(
            f'    {name}: {py2ts(ann, True)}'
            for name, ann in struct.__annotations__.items()
        )
)
for struct in structs
    ))
    

def dump_api(template_file: str, dst: str) -> None:
    with open(template_file, encoding='utf-8') as file:
        template = file.read()
    write_file(dst, re.sub(r'//--METHODS START----[\s\S]*//--METHODS END----', '\n'.join(
"""  /**
   * {doc}
   * ### [{method}] {url}
   * #### 权限: {permission}{comment_params}
   */
  {name}({params}): ForegroundApiRunner<{returns}> {{
    return createForegroundApiRunner({function_args});
  }}
""".format(
        doc=api.doc or '',
        method=api.method,
        url=api.url.string,
        permission=api.permission,
        comment_params='' if not total_params else '\n' + '\n'.join(
            f'   * @param {name}'
            for name in total_params
        ),
        name=snake2camel(api.name),
        params='' if not total_params else '\n' + ',\n'.join(
            f'    {name}: {py2ts(ann, False)}'
            for name, ann in total_params.items()
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
and (total_params := api.url.params | api.params)
or True
    ), template))


def main():
    try:
        with open('apimgr.json', encoding='utf-8') as file:
            cfg = argparse.Namespace(**json.load(file))
    except OSError:
        parser = argparse.ArgumentParser()
        parser.add_argument('-e', '--enum', required=True)
        parser.add_argument('-a', '--api', required=True)
        parser.add_argument('-s', '--struct', required=True)
        parser.add_argument('-t', '--api-template', required=True)
        parser.add_argument('-d', '--doc', required=True)
        cfg = parser.parse_args()
    dump_enum(cfg.enum)
    dump_api(cfg.api_template, cfg.api)
    dump_structs(cfg.struct)


if __name__ == '__main__':
    main()

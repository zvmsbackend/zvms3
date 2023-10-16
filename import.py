from argparse import ArgumentParser
from operator import itemgetter
from itertools import groupby

import sqlite3
import hashlib
import random
import csv


def md5ify(bytes: bytes) -> str:
    md5 = hashlib.md5()
    md5.update(bytes)
    return md5.hexdigest()


def generate_password(length: int) -> str:
    return md5ify(random.randbytes(8))[:length]


def chunks(n, iterable):
    iterator = iter(iterable)
    while True:
        ret = []
        try:
            for _ in range(n):
                ret.append(next(iterator))
            yield ret
        except StopIteration:
            yield ret
            return


def generate_html(users, classes) -> str:
    return '<html><body>{}</body></html>'.format(
        ''.join(
            generate_class_table(classes[classid], members)
            for classid, members in groupby(users, key=itemgetter(3))
        )
    )


def generate_class_table(classname, memebrs) -> str:
    return f'<h2>{classname}</h2><table>{{}}</table>'.format(
        ''.join(
            '<tr>{}</tr>'.format(
                ''.join(
                    f'<td>{userid}</td><td>{username}</td><td>{password}</td>'
                    for userid, username, password, _ in chunk
                )
            )
            for chunk in chunks(3, memebrs)
        )
    )


def main() -> None:
    parser = ArgumentParser()
    parser.add_argument('-c', '--classes',
                        default='classes.csv', help='班级的csv文件')
    parser.add_argument('-u', '--users', default='users.csv', help='用户的csv文件')
    parser.add_argument('-p', '--password-length', type=int,
                        default=8, help='初始密码的长度(1..32)')
    parser.add_argument('-o', '--output-password',
                        default='password.html', help='输出的密码html文件文件名')
    parser.add_argument('-a', '--admin', type=int, nargs='*',
                        help='设为超管的账户ID(若不指定, 则不设置超管)')
    args = parser.parse_args()

    with (open(args.classes, encoding='utf-8') as classes_file,
          open(args.users, encoding='utf-8') as users_file):
        classes = list(csv.reader(classes_file))[1:]
        users = list(csv.reader(users_file))[1:]
    connection = sqlite3.connect('instance/zvms.db')
    cursor = connection.cursor()

    cursor.executemany(
        'INSERT INTO class(id, name) '
        'VALUES(?, ?)',
        classes
    )
    users = [
        (id, name, generate_password(args.password_length), cls)
        for id, name, cls in users
    ]
    for id, name, pwd, cls in users:
        try:
            cursor.execute(
                'INSERT INTO user(userid, username, password, permission, classid) '
                'VALUES(?, ?, ?, 0, ?)',
                (id, name, md5ify(pwd), cls)
            )
        except sqlite3.IntegrityError as ex:
            msg, = ex.args
            if 'UNIQUE' in msg:
                print(id, msg)
                exit(1)
    open(args.output_password, 'w', encoding='utf-8').write(
        generate_html(users, dict(classes))
    )
    if args.admin is not None:
        cursor.executemany(
            'UPDATE user SET permission = 16 '
            'WHERE userid = ?',
            [(i,) for i in args.admin]
        )
    connection.commit()
    connection.close()


if __name__ == '__main__':
    main()

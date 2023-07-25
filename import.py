import argparse
import sqlite3
import hashlib
import random
import csv


def generate_password(length: int) -> str:
    md5 = hashlib.md5()
    md5.update(random.randbytes(8))
    return md5.hexdigest()[:length]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--classes',
                        default='classes.csv', help='班级的csv文件')
    parser.add_argument('-u', '--users', default='users.csv', help='用户的csv文件')
    parser.add_argument('-p', '--password-length', type=int,
                        default=8, help='初始密码的长度(1..32)')
    parser.add_argument('-o', '--output-password',
                        default='password.csv', help='输出的密码csv文件文件名')
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
    cursor.executemany(
        'INSERT INTO user(userid, username, password, permission, classid) '
        'VALUES(?, ?, ?, 0, ?)',
        users
    )
    open(args.output_password, 'w', encoding='utf-8').write(
        '\n'.join(
            f'{id}, {name}, {pwd}'
            for id, name, pwd, _ in users
        )
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

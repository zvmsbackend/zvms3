import argparse
import sqlite3
import hashlib
import random
import csv

def generate_password(length: int) -> str:
    md5 = hashlib.md5()
    md5.update(random.randbytes(8))
    return md5.hexdigest()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--classes', default='classes.csv')
    parser.add_argument('-u', '--users', default='users.csv')
    parser.add_argument('-p', '--password-length', type=int, default=8)
    parser.add_argument('-o', '--output-password', default='password.csv')
    parser.add_argument('-a', '--admin', type=int, nargs='?')
    args = parser.parse_args()
    classes = list(csv.reader(open(args.classes, encoding='utf-8')))[1:]
    users = list(csv.reader(open(args.users, encoding='utf-8')))[1:]
    connection = sqlite3.connect('instance/zvms.db')
    cursor = connection.cursor()
    cursor.executemany(
        'INSERT INTO class(id, name) '
        'VALUES(?, ?)',
        classes
    )
    users = [
        (id, name, generate_password(), cls)
        for id, name, cls in users
    ]
    cursor.executemany(
        'INSERT INTO user(userid, username, password, permission, classid) '
        'VALUES(?, ?, ?, 0, ?)',
        users
    )
    open(args.output_password, 'w', encoding='utf-8').write(
        '\n'.join(
            '{}, {}, {}'.format(id, name, pwd)
            for id, name, pwd, _ in users
        )
    )
    if args.admin is not None:
        cursor.execute(
            'UPDATE user SET permission = permission & 16 '
            'WHERE userid = ?',
            (args.admin)
        )

if __name__ == '__main__':
    main()
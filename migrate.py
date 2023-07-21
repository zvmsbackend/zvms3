from operator import itemgetter
import argparse
import sqlite3
import os.path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--old-database-path',
                        default='zvms.db', help='旧数据库的路径')
    args = parser.parse_args()

    conn_old = sqlite3.connect(args.old_database_path)
    conn_new = sqlite3.connect('instance/zvms.db')

    cur_old = conn_old.cursor()
    cur_new = conn_new.cursor()

    users = cur_old.execute(
        'SELECT id, name, class, pwd, auth FROM user'
    ).fetchall()
    names = list(map(itemgetter(1), users))
    users = [
        (id, n, pwd, {
            2: 0,
            10: 1,
            18: 2,
            26: 3,
            34: 4,
            42: 5,
            66: 16,
            130: 8,
            132: 8
        }[auth], cls)
        for id, name, cls, pwd, auth in users
        if (n := name if names.count(name) == 1
            else f'{name}{"J" if cls % 100 > 10 else ""}{cls % 10 or 10}'
            ) or True
    ]
    cur_new.executemany(
        'INSERT INTO user(userid, username, password, permission, classid) '
        'VALUES(?, ?, ?, ?, ?)',
        users
    )

    cur_old.execute(
        'SELECT id, name FROM class'
    )
    cur_new.executemany(
        'INSERT INTO class(id, name) VALUES(?, ?)',
        cur_old.fetchall()
    )

    cur_old.execute(
        'SELECT id, name, description, status, holder, type, reward, time FROM volunteer'
    )
    cur_new.executemany(
        'INSERT INTO volunteer(id, name, description, status, holder, type, reward, time) '
        'VALUES(?, ?, ?, ?, ?, ?, ?, ?)',
        cur_old.fetchall()
    )

    cur_old.execute(
        'SELECT status, reward, stu_id, vol_id, thought FROM stu_vol'
    )
    thoughts = [
        ({
            1: 1,
            2: 2,
            4: 3,
            5: 4,
            6: 5
        }[status], 0 if reward < 0 else reward, *spam)
        for status, reward, *spam in cur_old.fetchall()
    ]
    cur_new.executemany(
        'INSERT INTO user_vol(status, reward, userid, volid, thought) '
        'VALUES(?, ?, ?, ?, ?)',
        thoughts
    )

    cur_old.execute(
        'SELECT class_id, vol_id, max FROM class_vol'
    )
    cur_new.executemany(
        'INSERT INTO class_vol(classid, volid, max) '
        'VALUES(?, ?, ?)',
        cur_old.fetchall()
    )

    pictures = cur_old.execute(
        'SELECT stu_id, vol_id, hash, extension FROM picture'
    ).fetchall()
    for *_, digest, extension in pictures:
        path = os.path.join('zvms', 'static', 'pictures', digest)
        if os.path.exists(path):
            os.rename(path, os.path.join('zvms', 'static',
                                         'pictures', f'{digest}.{extension}'))
    cur_new.executemany(
        'INSERT INTO picture(userid, volid, filename) '
        'VALUES(?, ?, ?)',
        ((*spam, f'{digest}.{extension}')
         for *spam, digest, extension in pictures)
    )

    conn_new.commit()
    conn_new.close()


if __name__ == '__main__':
    main()

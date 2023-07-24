CREATE TABLE IF NOT EXISTS user(
    userid INT PRIMARY KEY,
    username VARCHAR(5) UNIQUE,
    password CHAR(32),
    permission SMALLINT,
    classid INT,
    FOREIGN KEY (classid) REFERENCES class(id)
);

CREATE TABLE IF NOT EXISTS class(
    id INT PRIMARY KEY,
    name VARCHAR(5)
);

CREATE TABLE IF NOT EXISTS volunteer(
    id INTEGER PRIMARY KEY AUTOINCREMENT, 
    name VARCHAR(32), 
    description TEXT,
    status SMALLINT,
    holder INT, 
    type SMALLINT, 
    reward INT,
    time DATE,
    FOREIGN KEY (holder) REFERENCES user(userid)
);

CREATE TABLE IF NOT EXISTS user_vol(
    userid INT, 
    volid INT, 
    status SMALLINT, 
    thought TEXT,
    reward INT, 
    PRIMARY KEY(userid, volid),
    FOREIGN KEY (userid) REFERENCES user(userid),
    FOREIGN KEY (volid) REFERENCES volunteer(id)
);

CREATE TABLE IF NOT EXISTS class_vol(
    classid INT,
    volid INT,
    max INT,
    PRIMARY KEY (classid, volid),
    FOREIGN KEY (classid) REFERENCES class(id),
    FOREIGN KEY (volid) REFERENCES volunteers(id)
);

CREATE TABLE IF NOT EXISTS picture(
    userid INT,
    volid INT,
    filename VARCHAR(36),
    FOREIGN KEY (userid) REFERENCES users(userid),
    FOREIGN KEY (volid) REFERENCES volunteer(id)
);

CREATE TABLE IF NOT EXISTS issue(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    author INT,
    content VARCHAR(64),
    time DATETIME,
    FOREIGN KEY (author) REFERENCES user(userid)
);

CREATE TABLE IF NOT EXISTS notice(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title VARCHAR(32),
    content TEXT,
    sender INT,
    school BOOLEAN,
    expire DATETIME,
    FOREIGN KEY (sender) REFERENCES user(userid)
);

CREATE TABLE IF NOT EXISTS user_notice(
    userid INT,
    noticeid INT,
    PRIMARY KEY (userid, noticeid),
    FOREIGN KEY (userid) REFERENCES user(userid),
    FOREIGN KEY (noticeid) REFERENCES notice(id)
);

CREATE TABLE IF NOT EXISTS class_notice(
    classid INT,
    noticeid INT,
    PRIMARY KEY (classid, noticeid),
    FOREIGN KEY (classid) REFERENCES class(id),
    FOREIGN KEY (noticeid) REFERENCES notice(id) 
);

INSERT INTO class(id, name) VALUES(0, '义管会');

INSERT INTO user(userid, username, password, permission, classid) VALUES(0, '系统', '', 0, 0);

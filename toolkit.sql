CREATE TABLE IF NOT EXISTS birthday(
    userid INT PRIMARY KEY,
    year INT,
    month INT,
    day INT,
    FOREIGN KEY (userid) REFERENCES user(userid)
);

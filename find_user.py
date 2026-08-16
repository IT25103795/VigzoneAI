import sqlite3
import glob

dbs = glob.glob('**/*.db', recursive=True)
print('DBs:', dbs)
for db in dbs:
    try:
        c = sqlite3.connect(db)
        print(db, c.execute('SELECT COUNT(*) FROM users').fetchone())
        row = c.execute('SELECT email, role, plan FROM users WHERE email LIKE "%bhashithanavod%"').fetchone()
        print('User:', row)
        c.execute('UPDATE users SET role="admin" WHERE email LIKE "%bhashithanavod%"')
        c.commit()
    except Exception as e:
        print(db, 'error', e)

from auth import _connect
import uuid
import datetime

def run():
    with _connect() as conn:
        # Check if 808 exists
        row = conn.execute("SELECT id FROM users WHERE email='bhashithanavod808@gmail.com'").fetchone()
        if not row:
            session_token = str(uuid.uuid4())
            conn.execute('''
                INSERT INTO users (email, role, plan, created_at, session_token) 
                VALUES ('bhashithanavod808@gmail.com', 'admin', 'pro', ?, ?)
            ''', (datetime.datetime.utcnow().isoformat(), session_token))
            print("Inserted bhashithanavod808@gmail.com as admin/pro.")
        else:
            conn.execute("UPDATE users SET role='admin', plan='pro' WHERE email='bhashithanavod808@gmail.com'")
            print("Updated bhashithanavod808@gmail.com to admin/pro.")

run()

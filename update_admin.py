from auth import _connect

def run():
    with _connect() as conn:
        print("Backend:", type(conn).__name__)
        # Find user
        row = conn.execute("SELECT email, role, plan FROM users WHERE email LIKE '%bhashithanavod808%'").fetchone()
        print("Admin user before:", row)
        
        # Update user to admin
        conn.execute("UPDATE users SET role='admin', plan='pro' WHERE email LIKE '%bhashithanavod808%'")
        
        row = conn.execute("SELECT email, role, plan FROM users WHERE email LIKE '%bhashithanavod808%'").fetchone()
        print("Admin user after:", row)

        # Look for the regular user who purchased PRO (we don't know the email, let's list all PRO users)
        rows = conn.execute("SELECT email, role, plan FROM users WHERE plan='pro'").fetchall()
        print("All PRO users:", rows)
        
run()

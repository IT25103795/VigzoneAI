from auth import _connect

def run():
    with _connect() as conn:
        rows = conn.execute("SELECT email, role, plan FROM users").fetchall()
        print("All users:")
        for r in rows:
            print(tuple(r))
        
run()

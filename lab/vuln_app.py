"""INTENTIONALLY VULNERABLE lab app for the SQL injection lesson. Fake data only.
Binds to 127.0.0.1 only. Never expose this to a network. Run: python lab/vuln_app.py"""
import json
import sqlite3
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

HOST, PORT = "127.0.0.1", 8099
assert HOST in ("127.0.0.1", "::1", "localhost"), "this deliberately vulnerable app must only listen on loopback"
db = sqlite3.connect(":memory:", check_same_thread=False)
db.executescript("""
create table products(id integer primary key, name text, price real);
insert into products(name, price) values ('laptop', 899.0), ('laptop bag', 29.0), ('monitor', 199.0);
create table users(id integer primary key, username text, password text, role text);
insert into users(username, password, role) values ('admin', 'lab-only-not-real', 'admin'), ('alice', 'lab-only-not-real-2', 'user');
""")


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if u.path == "/search":  # VULNERABLE: string concatenation
                rows = db.execute("SELECT name, price FROM products WHERE name LIKE '%" + q.get("q", "") + "%'").fetchall()
                return self.send(200, {"results": rows})
            if u.path == "/login":  # VULNERABLE: string concatenation
                row = db.execute("SELECT username, role FROM users WHERE username='" + q.get("user", "") + "' AND password='" + q.get("pass", "") + "'").fetchone()
                return self.send(200 if row else 401, {"user": row[0], "role": row[1]} if row else {"error": "invalid credentials"})
            if u.path == "/safe/search":  # FIXED: bound parameter
                rows = db.execute("SELECT name, price FROM products WHERE name LIKE ?", ("%" + q.get("q", "") + "%",)).fetchall()
                return self.send(200, {"results": rows})
            self.send(404, {"error": "not found"})
        except sqlite3.Error as e:
            self.send(500, {"error": str(e)})


if __name__ == "__main__":
    HTTPServer((HOST, PORT), H).serve_forever()

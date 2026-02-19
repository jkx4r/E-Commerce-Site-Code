import http.server
import socketserver
import sqlite3
import os
import urllib.parse
import json
from http import cookies

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'shop_data.db')
PORT = 8000

# --- DATABASE INIT ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, role TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS products 
                 (id INTEGER PRIMARY KEY, name TEXT, price REAL, img TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS carts 
                 (id INTEGER PRIMARY KEY, username TEXT, product_id INTEGER, quantity INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS addresses 
                 (id INTEGER PRIMARY KEY, username TEXT, address_text TEXT)''')
    
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO users (username, password, role) VALUES (?,?,?)", 
                  ('admin', 'admin', 'admin'))
    conn.commit()
    conn.close()

# --- HTML TEMPLATES ---
def get_header(user=None):
    nav_links = '<a href="/" class="hover:text-indigo-600 transition">Home</a>'
    
    # MODIFIED: Only show Cart if user is NOT an admin
    if user and user['role'] != 'admin':
        nav_links += '<a href="/cart" class="hover:text-indigo-600 transition ml-4">🛒 Cart</a>'
        
    if user and user['role'] == 'admin':
        nav_links += '<a href="/admin" class="hover:text-indigo-600 transition ml-4">Dashboard</a>'
    
    if user:
        auth_link = f'''
            <a href="/profile" class="text-indigo-600 font-medium hover:underline mr-4">Edit Profile</a>
            <span class="text-gray-500 mr-2">Hi, {user['name']}</span>
            <a href="/logout" class="text-red-500 hover:text-red-700">Logout</a>'''
    else:
        auth_link = '''
            <a href="/login" class="text-indigo-600 font-medium hover:underline">Login</a>
            <a href="/register" class="bg-indigo-600 text-white px-4 py-2 rounded-lg hover:bg-indigo-700 transition ml-4">Register</a>'''
    
    return f'''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Techify</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&display=swap" rel="stylesheet">
        <style>
            body {{ font-family: 'Inter', sans-serif; }}
            .aspect-square-crop {{ position: relative; width: 100%; padding-top: 100%; overflow: hidden; background-color: #f3f4f6; }}
            .aspect-square-crop img {{ position: absolute; top: 0; left: 0; width: 100%; height: 100%; object-fit: cover; transition: transform 0.5s ease; }}
            .group:hover .aspect-square-crop img {{ transform: scale(1.1); }}
            .thumb-crop {{ width: 80px; height: 80px; object-fit: cover; border-radius: 12px; border: 1px solid #e5e7eb; }}
        </style>
    </head>
    <body class="bg-gray-50 text-gray-800">
        <nav class="bg-white shadow-md sticky top-0 z-50">
            <div class="max-w-6xl mx-auto px-4 py-4 flex justify-between items-center">
                <a href="/" class="text-2xl font-bold text-indigo-600 flex items-center gap-2">
                    <span class="text-3xl">🛍️</span> Techify
                </a>
                <div class="flex items-center space-x-6 font-medium">
                    {nav_links}
                    {auth_link}
                </div>
            </div>
        </nav>
    '''

class ShopHandler(http.server.BaseHTTPRequestHandler):
    def get_user(self):
        cookie = cookies.SimpleCookie(self.headers.get('Cookie'))
        if 'user' in cookie:
            username = cookie['user'].value
            conn = sqlite3.connect(DB_PATH)
            res = conn.execute("SELECT role FROM users WHERE username=?", (username,)).fetchone()
            conn.close()
            return {'name': username, 'role': res[0]} if res else None
        return None

    def do_GET(self):
        user = self.get_user()
        parsed_path = urllib.parse.urlparse(self.path)
        query_params = urllib.parse.parse_qs(parsed_path.query)
        
        if parsed_path.path == '/':
            search_query = query_params.get('q', [''])[0]
            conn = sqlite3.connect(DB_PATH)
            products = conn.execute("SELECT * FROM products WHERE name LIKE ?", (f'%{search_query}%',)).fetchall() if search_query else conn.execute("SELECT * FROM products").fetchall()
            conn.close()
            items_html = ""
            for p in products:
                # MODIFIED: Do not show "Add to Cart" button if user is an Admin
                cart_form = ""
                if not user or user['role'] != 'admin':
                    cart_form = f'''<form action="/cart/add" method="POST"><input type="hidden" name="product_id" value="{p[0]}">
                                    <button type="submit" class="w-full mt-4 bg-gray-900 text-white py-3 rounded-2xl font-semibold hover:bg-indigo-600 transition-all active:scale-95">Add to Cart</button></form>'''
                
                items_html += f'''
                <div class="bg-white rounded-3xl shadow-sm border border-gray-100 hover:shadow-xl transition group overflow-hidden">
                    <div class="aspect-square-crop"><img src="{p[3] if p[3] else "https://via.placeholder.com/400"}"></div>
                    <div class="p-6">
                        <h3 class="text-lg font-bold text-gray-900 truncate">{p[1]}</h3>
                        <p class="text-indigo-600 font-extrabold text-xl mt-1">${p[2]:,.2f}</p>
                        {cart_form}
                    </div>
                </div>'''
            search_bar = f'<form action="/" method="GET" class="mb-10 flex gap-3"><input name="q" value="{search_query}" placeholder="Search products..." class="flex-1 border p-4 rounded-2xl outline-none focus:ring-4 focus:ring-indigo-100 border-gray-200 shadow-sm transition"><button class="bg-indigo-600 text-white px-8 py-4 rounded-2xl font-bold">Search</button></form>'
            self.send_html(get_header(user) + f'<div class="max-w-6xl mx-auto p-6"><h1 class="text-4xl font-extrabold mb-8 text-gray-900 tracking-tight">Discover Collection</h1>{search_bar}<div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-8">{items_html}</div></div>')

        elif parsed_path.path == '/register':
            error_msg = ""
            err_type = query_params.get('error', [''])[0]
            if err_type == 'short_user': error_msg = "Username must be at least 3 characters."
            elif err_type == 'short_pass': error_msg = "Password must be at least 8 characters."
            elif err_type == 'exists': error_msg = "Username already exists."
            self.send_html(get_header(user) + f'<div class="max-w-md mx-auto mt-20 p-10 bg-white rounded-3xl shadow-xl border"><h2 class="text-3xl font-bold text-center mb-6">Create Account</h2><p class="text-red-500 text-center mb-4">{error_msg}</p><form action="/register" method="POST" class="space-y-4"><input name="user" placeholder="Username" class="w-full border p-4 rounded-2xl outline-none" required><input name="pass" type="password" placeholder="Password" class="w-full border p-4 rounded-2xl outline-none" required><button class="w-full bg-indigo-600 text-white py-4 rounded-2xl font-bold hover:bg-indigo-700 transition">Register</button></form></div>')

        elif parsed_path.path == '/login':
            self.send_html(get_header(user) + '<div class="max-w-md mx-auto mt-20 p-10 bg-white rounded-3xl shadow-xl border"><h2 class="text-3xl font-bold text-center mb-6">Login</h2><form action="/login" method="POST" class="space-y-4"><input name="user" placeholder="Username" class="w-full border p-4 rounded-2xl outline-none" required><input name="pass" type="password" placeholder="Password" class="w-full border p-4 rounded-2xl outline-none" required><button class="w-full bg-indigo-600 text-white py-4 rounded-2xl font-bold hover:bg-indigo-700 transition">Sign In</button></form></div>')

        elif parsed_path.path == '/admin':
            if not user or user['role'] != 'admin': self.redirect('/login'); return
            conn = sqlite3.connect(DB_PATH)
            products = conn.execute("SELECT * FROM products").fetchall()
            conn.close()
            rows = "".join([f'<tr class="border-b"><td class="p-4">#{p[0]}</td><td class="p-4"><img src="{p[3]}" class="thumb-crop"></td><td class="p-4 font-bold">{p[1]}</td><td class="p-4 text-indigo-600 font-bold">${p[2]:,.2f}</td><td class="p-4"><a href="/admin/delete?id={p[0]}" class="text-red-500 font-semibold hover:underline">Delete</a></td></tr>' for p in products])
            self.send_html(get_header(user) + f'<div class="max-w-5xl mx-auto p-6"><div class="bg-white p-10 rounded-3xl shadow-sm border mb-8"><h2 class="text-2xl font-bold mb-6">Add New Product</h2><form action="/admin/add" method="POST" class="grid grid-cols-1 md:grid-cols-4 gap-4"><input name="name" placeholder="Name" class="border p-3 rounded-xl outline-none" required><input name="price" type="number" step="0.01" placeholder="Price" class="border p-3 rounded-xl outline-none" required><input name="img" placeholder="Image URL" class="border p-3 rounded-xl outline-none"><button class="bg-indigo-600 text-white py-3 rounded-xl font-bold hover:bg-indigo-700 transition">Add Item</button></form></div><div class="bg-white p-6 rounded-3xl shadow-sm border overflow-hidden"><h2 class="text-2xl font-bold mb-6 px-4 pt-4 text-gray-900">Inventory</h2><table class="w-full text-left"><thead><tr class="bg-gray-50 border-b text-gray-500 uppercase text-xs tracking-wider"><th class="p-4">ID</th><th class="p-4">Preview</th><th class="p-4">Name</th><th class="p-4">Price</th><th class="p-4">Action</th></tr></thead><tbody>{rows}</tbody></table></div></div>')

        elif parsed_path.path == '/profile':
            if not user: self.redirect('/login'); return
            addr_section = ""
            if user['role'] != 'admin':
                conn = sqlite3.connect(DB_PATH)
                addr_list = conn.execute("SELECT id, address_text FROM addresses WHERE username = ?", (user['name'],)).fetchall()
                conn.close()
                addr_html = "".join([f'<div class="p-4 bg-gray-50 rounded-xl mb-3 border flex justify-between items-center group"><span>{a[1]}</span><div class="flex gap-3"><button onclick="document.getElementById(\'edit-addr-{a[0]}\').classList.toggle(\'hidden\')" class="text-indigo-400 font-bold">Edit</button><a href="/profile/address/delete?id={a[0]}" class="text-red-400 font-bold">×</a></div></div><form id="edit-addr-{a[0]}" action="/profile/address/edit" method="POST" class="hidden mb-4 p-4 border rounded-xl bg-white shadow-inner"><input type="hidden" name="id" value="{a[0]}"><textarea name="address" class="w-full border p-2 rounded-lg text-sm" required>{a[1]}</textarea><button class="bg-indigo-600 text-white px-4 py-2 rounded-xl mt-2 text-xs font-bold">Save Changes</button></form>' for a in addr_list])
                addr_error = "Limit reached (Max 3 addresses)." if query_params.get('error', [''])[0] == 'limit' else ""
                addr_section = f'''<hr class="my-8"><h3 class="font-bold text-lg mb-4 text-gray-900">Shipping Addresses (Max 3)</h3><p class="text-red-500 text-xs mb-3">{addr_error}</p>{addr_html if addr_list else '<p class="text-sm text-gray-400 mb-6 italic">No addresses saved yet.</p>'}{f'<form action="/profile/address/add" method="POST" class="mt-6"><textarea name="address" class="w-full border border-gray-200 p-4 rounded-2xl text-sm mb-3 outline-none focus:ring-2 focus:ring-indigo-100" placeholder="Enter full address here..." required></textarea><button class="bg-gray-900 text-white text-sm px-6 py-3 rounded-2xl font-bold hover:bg-gray-800 transition shadow-lg">Add New Address</button></form>' if len(addr_list) < 3 else ''}'''
            success_msg = "Profile updated successfully!" if query_params.get('success', [''])[0] == '1' else ""
            self.send_html(get_header(user) + f'''<div class="max-w-md mx-auto mt-10 p-10 bg-white rounded-[2rem] shadow-2xl border border-gray-100"><h2 class="text-3xl font-extrabold text-center mb-8 text-gray-900">Account Settings</h2><p class="text-green-500 text-center mb-6 font-medium">{success_msg}</p><form action="/profile/update" method="POST" class="space-y-6 mb-10"><div class="space-y-1"><label class="block text-xs font-bold text-gray-400 uppercase tracking-widest ml-1">Username</label><input value="{user['name']}" class="w-full border-none p-4 rounded-2xl bg-gray-100 font-semibold text-gray-500 cursor-not-allowed" readonly></div><div class="space-y-1"><label class="block text-xs font-bold text-gray-400 uppercase tracking-widest ml-1">Update Password</label><input name="new_pass" type="password" placeholder="Min 8 characters" class="w-full border border-gray-200 p-4 rounded-2xl outline-none focus:ring-4 focus:ring-indigo-50/50"></div><button class="w-full bg-indigo-600 text-white py-4 rounded-2xl font-extrabold shadow-xl shadow-indigo-100 hover:bg-indigo-700 transition-all active:scale-95">Save Profile</button></form>{addr_section}</div>''')

        elif parsed_path.path == '/cart':
            # MODIFIED: Deny Admin access to the cart page
            if not user or user['role'] == 'admin': self.redirect('/'); return
            conn = sqlite3.connect(DB_PATH)
            cart_items = conn.execute('''SELECT products.name, products.price, carts.quantity, products.img, products.id, carts.id FROM carts JOIN products ON carts.product_id = products.id WHERE carts.username = ?''', (user['name'],)).fetchall()
            conn.close()
            items_html = ""
            for item in cart_items:
                items_html += f'''<div class="flex items-center justify-between border-b border-gray-50 py-6 cart-item" data-price="{item[1]}" id="item-{item[5]}">
                    <div class="flex items-center">
                        <input type="checkbox" name="selected" value="{item[4]}" class="cart-checkbox mr-6 w-6 h-6 rounded-lg border-gray-200 text-indigo-600 focus:ring-indigo-500 cursor-pointer" checked onchange="calc()">
                        <img src="{item[3] if item[3] else "https://via.placeholder.com/200"}" class="thumb-crop mr-6 shadow-sm">
                        <div class="space-y-1">
                            <h4 class="font-bold text-gray-900">{item[0]}</h4>
                            <p class="text-gray-400 text-xs">${item[1]:,.2f} per unit</p>
                            <div class="flex items-center gap-3 pt-2">
                                <form action="/cart/qty" method="POST"><input type="hidden" name="id" value="{item[5]}"><input type="hidden" name="change" value="-1"><button class="w-8 h-8 bg-gray-100 flex items-center justify-center rounded-lg hover:bg-gray-200 transition">-</button></form>
                                <span class="qty-display font-bold text-sm w-4 text-center">{item[2]}</span>
                                <form action="/cart/qty" method="POST"><input type="hidden" name="id" value="{item[5]}"><input type="hidden" name="change" value="1"><button class="w-8 h-8 bg-gray-100 flex items-center justify-center rounded-lg hover:bg-gray-200 transition">+</button></form>
                                <a href="/cart/delete?id={item[5]}" class="ml-6 text-xs font-bold text-red-400 hover:text-red-600">Remove</a>
                            </div>
                        </div></div>
                    <div class="font-extrabold text-gray-900 text-lg">${(item[1]*item[2]):,.2f}</div></div>'''
            
            script = '''<script>
                function calc() {
                    let total = 0;
                    document.querySelectorAll('.cart-item').forEach(item => {
                        if(item.querySelector('.cart-checkbox').checked) {
                            let price = parseFloat(item.dataset.price);
                            let qty = parseInt(item.querySelector('.qty-display').innerText);
                            total += price * qty;
                        }
                    });
                    document.getElementById('total-display').innerText = '$' + total.toLocaleString(undefined, {minimumFractionDigits: 2});
                }
                window.onload = calc;
            </script>'''
            
            self.send_html(get_header(user) + f'''<div class="max-w-4xl mx-auto p-10 bg-white mt-10 rounded-[2.5rem] shadow-2xl border border-gray-50"><h2 class="text-4xl font-extrabold mb-10 text-gray-900 tracking-tight">Shopping Cart</h2>
                <div class="divide-y divide-gray-50">{items_html if cart_items else '<p class="text-gray-400 text-center py-20 text-lg font-medium italic">Your bag is currently empty.</p>'}<div class="mt-12 flex justify-between items-center p-8 bg-gray-50 rounded-[2rem]"><span class="text-xl font-bold text-gray-500">Selected Total</span><span class="text-4xl font-black text-indigo-600" id="total-display">$0.00</span></div>
                <div class="flex gap-6 mt-10"><button onclick="location.reload()" class="flex-1 border border-gray-200 py-5 rounded-2xl font-extrabold text-gray-500 hover:bg-gray-50 transition-all">Refresh Bag</button><button class="flex-[2] bg-indigo-600 text-white py-5 rounded-2xl font-extrabold shadow-xl shadow-indigo-100 hover:bg-indigo-700 transition-all active:scale-95">Checkout Selected</button></div></div></div>{script}''')

        elif parsed_path.path == '/logout':
            self.send_response(302); self.send_header('Set-Cookie', 'user=; Max-Age=0; Path=/'); self.send_header('Location', '/'); self.end_headers()

        elif parsed_path.path == '/admin/delete':
             if user and user['role'] == 'admin':
                pid = query_params.get('id', [None])[0]
                conn = sqlite3.connect(DB_PATH); conn.execute("DELETE FROM products WHERE id=?", (pid,)); conn.commit(); conn.close()
             self.redirect('/admin')
             
        elif parsed_path.path == '/profile/address/delete':
            if user:
                aid = query_params.get('id', [None])[0]
                conn = sqlite3.connect(DB_PATH); conn.execute("DELETE FROM addresses WHERE id=? AND username=?", (aid, user['name'])); conn.commit(); conn.close()
            self.redirect('/profile')

        elif parsed_path.path == '/cart/delete':
            if user:
                cid = query_params.get('id', [None])[0]
                conn = sqlite3.connect(DB_PATH); conn.execute("DELETE FROM carts WHERE id=? AND username=?", (cid, user['name'])); conn.commit(); conn.close()
            self.redirect('/cart')

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        data = urllib.parse.parse_qs(self.rfile.read(length).decode())
        user_session = self.get_user()

        if self.path == '/register':
            u, p = data.get('user', [''])[0], data.get('pass', [''])[0]
            if len(u) < 3 or len(p) < 8: self.redirect('/register?error=short_user' if len(u)<3 else '/register?error=short_pass'); return
            conn = sqlite3.connect(DB_PATH)
            try: conn.execute("INSERT INTO users (username, password, role) VALUES (?,?,?)", (u, p, 'customer')); conn.commit(); self.redirect('/login')
            except: self.redirect('/register?error=exists')
            finally: conn.close()

        elif self.path == '/login':
            u, p = data.get('user', [''])[0], data.get('pass', [''])[0]
            conn = sqlite3.connect(DB_PATH); res = conn.execute("SELECT role FROM users WHERE username=? AND password=?", (u, p)).fetchone(); conn.close()
            if res: self.send_response(302); self.send_header('Set-Cookie', f'user={u}; Path=/; HttpOnly'); self.send_header('Location', '/'); self.end_headers()
            else: self.redirect('/login?error=1')

        elif self.path == '/profile/update':
            if not user_session: self.redirect('/login'); return
            np = data.get('new_pass', [''])[0]
            if np:
                if len(np) < 8: self.redirect('/profile?error=short_pass'); return
                conn = sqlite3.connect(DB_PATH); conn.execute("UPDATE users SET password=? WHERE username=?", (np, user_session['name'])); conn.commit(); conn.close()
            self.redirect('/profile?success=1')

        elif self.path == '/profile/address/add':
            if not user_session: self.redirect('/login'); return
            addr = data.get('address', [''])[0]
            conn = sqlite3.connect(DB_PATH)
            count = conn.execute("SELECT count(*) FROM addresses WHERE username=?", (user_session['name'],)).fetchone()[0]
            if count >= 3: conn.close(); self.redirect('/profile?error=limit'); return
            conn.execute("INSERT INTO addresses (username, address_text) VALUES (?, ?)", (user_session['name'], addr)); conn.commit(); conn.close()
            self.redirect('/profile')

        elif self.path == '/profile/address/edit':
            if not user_session: self.redirect('/login'); return
            aid, addr = data.get('id', [''])[0], data.get('address', [''])[0]
            conn = sqlite3.connect(DB_PATH); conn.execute("UPDATE addresses SET address_text=? WHERE id=? AND username=?", (addr, aid, user_session['name'])); conn.commit(); conn.close()
            self.redirect('/profile')

        elif self.path == '/cart/qty':
            # MODIFIED: Deny Admin ability to change cart quantities
            if not user_session or user_session['role'] == 'admin': self.redirect('/'); return
            cid, change = data.get('id', [''])[0], int(data.get('change', ['0'])[0])
            conn = sqlite3.connect(DB_PATH)
            conn.execute('UPDATE carts SET quantity = quantity + ? WHERE id = ? AND username = ?', (change, cid, user_session['name']))
            conn.execute('DELETE FROM carts WHERE id = ? AND quantity < 1', (cid,))
            conn.commit(); conn.close(); self.redirect('/cart')

        elif self.path == '/admin/add':
            if user_session and user_session['role'] == 'admin':
                n, pr, i = data.get('name', [''])[0], data.get('price', ['0'])[0], data.get('img', [''])[0]
                conn = sqlite3.connect(DB_PATH); conn.execute("INSERT INTO products (name, price, img) VALUES (?,?,?)", (n, float(pr), i)); conn.commit(); conn.close()
            self.redirect('/admin')

        elif self.path == '/cart/add':
            # MODIFIED: Deny Admin ability to add items to cart
            if not user_session or user_session['role'] == 'admin': self.redirect('/'); return
            pid = data.get('product_id', [''])[0]
            conn = sqlite3.connect(DB_PATH)
            existing = conn.execute('SELECT quantity FROM carts WHERE username = ? AND product_id = ?', (user_session['name'], pid)).fetchone()
            if existing: conn.execute('UPDATE carts SET quantity = quantity + 1 WHERE username = ? AND product_id = ?', (user_session['name'], pid))
            else: conn.execute('INSERT INTO carts (username, product_id, quantity) VALUES (?, ?, ?)', (user_session['name'], pid, 1))
            conn.commit(); conn.close(); self.redirect('/')

    def send_html(self, content):
        self.send_response(200); self.send_header('Content-type', 'text/html; charset=utf-8'); self.end_headers(); self.wfile.write(content.encode())

    def redirect(self, path):
        self.send_response(302); self.send_header('Location', path); self.end_headers()

if __name__ == "__main__":
    init_db()
    print(f" Running at http://localhost:{PORT}")
    socketserver.TCPServer(("", PORT), ShopHandler).serve_forever()
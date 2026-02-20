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
                 (id INTEGER PRIMARY KEY, name TEXT, price REAL, img TEXT, description TEXT)''')
    
    # FIX: Automatic migration if column is missing from old database files
    try:
        c.execute("SELECT description FROM products LIMIT 1")
    except sqlite3.OperationalError:
        c.execute("ALTER TABLE products ADD COLUMN description TEXT")
        
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
    if user and user['role'] != 'admin':
        nav_links += '<a href="/cart" class="hover:text-indigo-600 transition ml-4">🛒 Cart</a>'
    if user and user['role'] == 'admin':
        nav_links += '<a href="/admin" class="hover:text-indigo-600 transition ml-4 font-bold text-indigo-600">📊 Admin</a>'
    
    auth_link = f'''
        <a href="/profile" class="text-indigo-600 font-medium hover:underline mr-4">Edit Profile</a>
        <span class="text-gray-500 mr-2">Hi, {user['name']}</span>
        <a href="/logout" class="text-red-500 hover:text-red-700">Logout</a>''' if user else '''
        <a href="/login" class="text-indigo-600 font-medium hover:underline">Login</a>
        <a href="/register" class="bg-indigo-600 text-white px-4 py-2 rounded-lg hover:bg-indigo-700 transition ml-4">Register</a>'''
    
    return f'''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Techify Store</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&display=swap" rel="stylesheet">
        <style>
            body {{ font-family: 'Inter', sans-serif; }}
            .aspect-square-crop {{ position: relative; width: 100%; padding-top: 100%; overflow: hidden; background-color: #f3f4f6; }}
            .aspect-square-crop img {{ position: absolute; top: 0; left: 0; width: 100%; height: 100%; object-fit: cover; transition: transform 0.5s ease; }}
            .group:hover .aspect-square-crop img {{ transform: scale(1.05); }}
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
            # Fetch specifically to avoid index errors
            products = conn.execute("SELECT id, name, price, img, description FROM products WHERE name LIKE ?", (f'%{search_query}%',)).fetchall()
            conn.close()
            items_html = ""
            for p in products:
                # Add to cart is separate at the bottom
                cart_btn = f'''<form action="/cart/add" method="POST" class="mt-auto">
                                <input type="hidden" name="product_id" value="{p[0]}">
                                <button type="submit" class="w-full bg-indigo-600 text-white py-3 rounded-2xl font-semibold hover:bg-indigo-700 transition-all active:scale-95 shadow-lg shadow-indigo-100">Add to Cart</button>
                               </form>''' if not user or user['role'] != 'admin' else ""
                
                items_html += f'''
                <div class="bg-white rounded-[2rem] shadow-sm border border-gray-100 hover:shadow-xl transition group overflow-hidden flex flex-col h-full">
                    <a href="/product?id={p[0]}" class="block">
                        <div class="aspect-square-crop"><img src="{p[3] if p[3] else "https://via.placeholder.com/400"}"></div>
                        <div class="p-6 pb-2">
                            <h3 class="text-lg font-bold text-gray-900 truncate group-hover:text-indigo-600 transition">{p[1]}</h3>
                            <p class="text-indigo-600 font-extrabold text-xl mt-1">${p[2]:,.2f}</p>
                            <p class="text-gray-400 text-xs mt-2 line-clamp-1 italic">Click to view description</p>
                        </div>
                    </a>
                    <div class="p-6 pt-0 mt-auto">
                        {cart_btn}
                    </div>
                </div>'''
            search_bar = f'<form action="/" method="GET" class="mb-10 flex gap-3"><input name="q" value="{search_query}" placeholder="Search products..." class="flex-1 border p-4 rounded-2xl outline-none focus:ring-4 focus:ring-indigo-100 border-gray-200 shadow-sm transition"><button class="bg-indigo-600 text-white px-8 py-4 rounded-2xl font-bold">Search</button></form>'
            self.send_html(get_header(user) + f'<div class="max-w-6xl mx-auto p-6"><h1 class="text-4xl font-extrabold mb-8 text-gray-900 tracking-tight">Store Collection</h1>{search_bar}<div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-8">{items_html}</div></div>')

        elif parsed_path.path == '/product':
            pid = query_params.get('id', [None])[0]
            conn = sqlite3.connect(DB_PATH)
            p = conn.execute("SELECT id, name, price, img, description FROM products WHERE id=?", (pid,)).fetchone()
            conn.close()
            if not p: self.redirect('/'); return

            cart_btn = f'''
                <form action="/cart/add" method="POST" class="mt-8">
                    <input type="hidden" name="product_id" value="{p[0]}">
                    <button type="submit" class="w-full md:w-auto bg-indigo-600 text-white px-12 py-4 rounded-2xl font-bold shadow-xl shadow-indigo-100 hover:bg-indigo-700 transition active:scale-95">Add to Cart</button>
                </form>''' if not user or user['role'] != 'admin' else ""

            content = f'''
            <div class="max-w-6xl mx-auto p-6 mt-10">
                <div class="bg-white rounded-[2.5rem] shadow-2xl border border-gray-50 overflow-hidden flex flex-col md:flex-row">
                    <div class="md:w-1/2 bg-gray-50 flex items-center justify-center p-8">
                        <img src="{p[3]}" class="max-w-full h-auto rounded-3xl shadow-lg">
                    </div>
                    <div class="md:w-1/2 p-10 md:p-16 flex flex-col justify-center">
                        <a href="/" class="text-indigo-600 font-bold text-sm uppercase tracking-widest mb-4 inline-block hover:underline">← Back to Home</a>
                        <h1 class="text-4xl md:text-5xl font-black text-gray-900 mb-4">{p[1]}</h1>
                        <p class="text-3xl font-bold text-indigo-600 mb-8">${p[2]:,.2f}</p>
                        <div>
                            <h3 class="text-gray-400 text-xs font-bold uppercase tracking-wider mb-2">Description</h3>
                            <p class="text-gray-600 leading-relaxed text-lg">{p[4] if p[4] else "No description available."}</p>
                        </div>
                        {cart_btn}
                    </div>
                </div>
            </div>'''
            self.send_html(get_header(user) + content)

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
            
            # Aggregate stats for Graph
            stats = conn.execute('''SELECT products.name, SUM(carts.quantity) FROM carts JOIN products ON carts.product_id = products.id GROUP BY products.id ORDER BY SUM(carts.quantity) DESC''').fetchall()
            chart_labels = [s[0] for s in stats]
            chart_data = [s[1] for s in stats]

            products = conn.execute("SELECT id, name, price, img, description FROM products").fetchall()
            conn.close()
            
            rows = "".join([f'''<tr class="border-b">
                    <td class="p-4 text-xs">#{p[0]}</td>
                    <td class="p-4"><img src="{p[3]}" class="thumb-crop"></td>
                    <td class="p-4 font-bold">{p[1]}</td>
                    <td class="p-4">
                        <form action="/admin/update_item" method="POST" class="flex flex-col gap-2">
                            <input type="hidden" name="id" value="{p[0]}">
                            <textarea name="desc" class="text-xs border p-2 rounded w-full h-20" placeholder="Description...">{p[4] if p[4] else ""}</textarea>
                            <div class="flex gap-2 items-center">
                                <input name="price" type="number" step="0.01" value="{p[2]}" class="border text-xs p-1 rounded w-20">
                                <button class="bg-indigo-500 text-white text-[10px] px-2 py-1 rounded">Update</button>
                            </div>
                        </form>
                    </td>
                    <td class="p-4 text-center"><a href="/admin/delete?id={p[0]}" class="text-red-500 font-semibold hover:underline text-xs">Delete</a></td>
                </tr>''' for p in products])

            self.send_html(get_header(user) + f'''<div class="max-w-6xl mx-auto p-6">
                <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-10">
                    <div class="lg:col-span-2 bg-white p-8 rounded-3xl border shadow-sm">
                        <h3 class="font-bold mb-4">Cart Demand Report</h3>
                        <canvas id="cartChart" height="150"></canvas>
                    </div>
                    <div class="bg-indigo-600 text-white p-8 rounded-3xl shadow-xl flex flex-col justify-center">
                        <h3 class="opacity-80">Highest Demand</h3>
                        <p class="text-2xl font-black mt-2">{(chart_labels[0] if chart_labels else "No Data")}</p>
                    </div>
                </div>
                <div class="bg-white p-10 rounded-3xl shadow-sm border mb-8"><h2 class="text-2xl font-bold mb-6">Add New Product</h2><form action="/admin/add" method="POST" class="grid grid-cols-1 md:grid-cols-4 gap-4"><input name="name" placeholder="Name" class="border p-3 rounded-xl outline-none" required><input name="price" type="number" step="0.01" placeholder="Price" class="border p-3 rounded-xl outline-none" required><input name="img" placeholder="Image URL" class="border p-3 rounded-xl outline-none"><textarea name="desc" placeholder="Description" class="border p-3 rounded-xl outline-none md:col-span-3"></textarea><button class="bg-indigo-600 text-white py-3 rounded-xl font-bold hover:bg-indigo-700 transition">Add Item</button></form></div>
                <div class="bg-white p-6 rounded-3xl shadow-sm border overflow-hidden"><h2 class="text-2xl font-bold mb-6 px-4 pt-4 text-gray-900">Inventory</h2><table class="w-full text-left"><thead><tr class="bg-gray-50 border-b uppercase text-xs"><th>ID</th><th>Preview</th><th>Name</th><th>Modify Details</th><th class="text-center">Action</th></tr></thead><tbody>{rows}</tbody></table></div>
            </div>
            <script>
                const ctx = document.getElementById('cartChart').getContext('2d');
                new Chart(ctx, {{
                    type: 'bar',
                    data: {{
                        labels: {json.dumps(chart_labels)},
                        datasets: [{{ label: 'Units in Carts', data: {json.dumps(chart_data)}, backgroundColor: '#6366f1', borderRadius: 10 }}]
                    }},
                    options: {{ responsive: true }}
                }});
            </script>''')

        elif parsed_path.path == '/cart':
            if not user or user['role'] == 'admin': self.redirect('/'); return
            conn = sqlite3.connect(DB_PATH)
            cart_items = conn.execute('''SELECT products.name, products.price, carts.quantity, products.img, products.id, carts.id, products.description FROM carts JOIN products ON carts.product_id = products.id WHERE carts.username = ?''', (user['name'],)).fetchall()
            conn.close()
            items_html = "".join([f'''<div class="flex items-center justify-between border-b border-gray-50 py-6 cart-item" data-price="{item[1]}" id="item-{item[5]}">
                    <div class="flex items-center">
                        <input type="checkbox" name="selected" class="cart-checkbox mr-6 w-6 h-6 rounded-lg border-gray-200 text-indigo-600" checked onchange="calc()">
                        <img src="{item[3] if item[3] else "https://via.placeholder.com/200"}" class="thumb-crop mr-6 shadow-sm">
                        <div class="space-y-1">
                            <h4 class="font-bold text-gray-900">{item[0]}</h4>
                            <p class="text-gray-400 text-xs line-clamp-1">{item[6] if item[6] else ''}</p>
                            <div class="flex items-center gap-3 pt-2">
                                <form action="/cart/qty" method="POST"><input type="hidden" name="product_id" value="{item[4]}"><input type="hidden" name="change" value="-1"><button class="w-8 h-8 bg-gray-100 rounded hover:bg-gray-200">-</button></form>
                                <span class="qty-display font-bold text-sm w-4 text-center">{item[2]}</span>
                                <form action="/cart/qty" method="POST"><input type="hidden" name="id" value="{item[5]}"><input type="hidden" name="product_id" value="{item[4]}"><input type="hidden" name="change" value="1"><button class="w-8 h-8 bg-gray-100 rounded hover:bg-gray-200">+</button></form>
                                <a href="/cart/delete?id={item[4]}" class="ml-6 text-xs font-bold text-red-400 hover:text-red-600">Remove</a>
                            </div>
                        </div></div>
                    <div class="font-extrabold text-gray-900 text-lg">${(item[1]*item[2]):,.2f}</div></div>''' for item in cart_items])
            
            script = '<script>function calc(){let t=0;document.querySelectorAll(".cart-item").forEach(i=>{if(i.querySelector(".cart-checkbox").checked){t+=parseFloat(i.dataset.price)*parseInt(i.querySelector(".qty-display").innerText)}});document.getElementById("total-display").innerText="$"+t.toLocaleString(undefined,{minimumFractionDigits:2})}window.onload=calc;</script>'
            self.send_html(get_header(user) + f'''<div class="max-w-4xl mx-auto p-10 bg-white mt-10 rounded-[2.5rem] shadow-2xl border border-gray-50"><h2 class="text-4xl font-extrabold mb-10 text-gray-900 tracking-tight">Shopping Cart</h2><div class="divide-y divide-gray-50">{items_html if cart_items else '<p class="text-gray-400 text-center py-20 text-lg font-medium italic">Bag is empty.</p>'}<div class="mt-12 flex justify-between items-center p-8 bg-gray-50 rounded-[2rem]"><span class="text-xl font-bold text-gray-500">Total</span><span class="text-4xl font-black text-indigo-600" id="total-display">$0.00</span></div><div class="flex gap-6 mt-10"><button onclick="location.reload()" class="flex-1 border py-5 rounded-2xl text-gray-500">Refresh</button><button class="flex-[2] bg-indigo-600 text-white py-5 rounded-2xl font-extrabold shadow-indigo-100 hover:bg-indigo-700 transition-all active:scale-95">Checkout</button></div></div></div>{script}''')

        elif parsed_path.path == '/profile':
            if not user: self.redirect('/login'); return
            addr_section = ""
            if user['role'] != 'admin':
                conn = sqlite3.connect(DB_PATH); addr_list = conn.execute("SELECT id, address_text FROM addresses WHERE username = ?", (user['name'],)).fetchall(); conn.close()
                addr_html = "".join([f'<div class="p-4 bg-gray-50 rounded-xl mb-3 border flex justify-between items-center group"><span>{a[1]}</span><div class="flex gap-3"><button onclick="document.getElementById(\'edit-addr-{a[0]}\').classList.toggle(\'hidden\')" class="text-indigo-400 font-bold">Edit</button><a href="/profile/address/delete?id={a[0]}" class="text-red-400 font-bold">×</a></div></div><form id="edit-addr-{a[0]}" action="/profile/address/edit" method="POST" class="hidden mb-4 p-4 border rounded-xl bg-white shadow-inner"><input type="hidden" name="id" value="{a[0]}"><textarea name="address" class="w-full border p-2 rounded-lg text-sm" required>{a[1]}</textarea><button class="bg-indigo-600 text-white px-4 py-2 rounded-xl mt-2 text-xs font-bold">Save Changes</button></form>' for a in addr_list])
                addr_section = f'''<hr class="my-8"><h3 class="font-bold text-lg mb-4 text-gray-900">Addresses (Max 3)</h3>{addr_html}{f'<form action="/profile/address/add" method="POST" class="mt-6"><textarea name="address" class="w-full border border-gray-200 p-4 rounded-2xl text-sm mb-3" placeholder="New address..." required></textarea><button class="bg-gray-900 text-white text-sm px-6 py-3 rounded-2xl font-bold">Add Address</button></form>' if len(addr_list) < 3 else ""}'''
            self.send_html(get_header(user) + f'''<div class="max-w-md mx-auto mt-10 p-10 bg-white rounded-[2rem] shadow-2xl border border-gray-100"><h2 class="text-3xl font-extrabold text-center mb-8">Account</h2><form action="/profile/update" method="POST" class="space-y-6 mb-10"><input value="{user['name']}" class="w-full p-4 rounded-2xl bg-gray-100" readonly><input name="new_pass" type="password" placeholder="New Password" class="w-full border p-4 rounded-2xl outline-none"><button class="w-full bg-indigo-600 text-white py-4 rounded-2xl font-extrabold transition-all active:scale-95">Save Profile</button></form>{addr_section}</div>''')

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
                pid = query_params.get('id', [None])[0]
                conn = sqlite3.connect(DB_PATH); conn.execute("DELETE FROM carts WHERE product_id=? AND username=?", (pid, user['name'])); conn.commit(); conn.close()
            self.redirect('/cart')

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        data = urllib.parse.parse_qs(self.rfile.read(length).decode())
        user_session = self.get_user()

        if self.path == '/register':
            u, p = data.get('user', [''])[0], data.get('pass', [''])[0]
            conn = sqlite3.connect(DB_PATH)
            try: conn.execute("INSERT INTO users (username, password, role) VALUES (?,?,?)", (u, p, 'customer')); conn.commit(); self.redirect('/login')
            except: self.redirect('/register?error=exists')
            finally: conn.close()

        elif self.path == '/login':
            u, p = data.get('user', [''])[0], data.get('pass', [''])[0]
            conn = sqlite3.connect(DB_PATH); res = conn.execute("SELECT role FROM users WHERE username=? AND password=?", (u, p)).fetchone(); conn.close()
            if res: self.send_response(302); self.send_header('Set-Cookie', f'user={u}; Path=/; HttpOnly'); self.send_header('Location', '/'); self.end_headers()
            else: self.redirect('/login?error=1')

        elif self.path == '/admin/update_item':
            if user_session and user_session['role'] == 'admin':
                pid, pr, d = data.get('id', [''])[0], data.get('price', ['0'])[0], data.get('desc', [''])[0]
                conn = sqlite3.connect(DB_PATH); conn.execute("UPDATE products SET price=?, description=? WHERE id=?", (float(pr), d, pid)); conn.commit(); conn.close()
            self.redirect('/admin')

        elif self.path == '/profile/update':
            if not user_session: self.redirect('/login'); return
            np = data.get('new_pass', [''])[0]
            if np:
                conn = sqlite3.connect(DB_PATH); conn.execute("UPDATE users SET password=? WHERE username=?", (np, user_session['name'])); conn.commit(); conn.close()
            self.redirect('/profile?success=1')

        elif self.path == '/profile/address/add':
            if not user_session: self.redirect('/login'); return
            addr = data.get('address', [''])[0]
            conn = sqlite3.connect(DB_PATH)
            count = conn.execute("SELECT count(*) FROM addresses WHERE username=?", (user_session['name'],)).fetchone()[0]
            if count < 3: conn.execute("INSERT INTO addresses (username, address_text) VALUES (?, ?)", (user_session['name'], addr)); conn.commit()
            conn.close(); self.redirect('/profile')

        elif self.path == '/profile/address/edit':
            if not user_session: self.redirect('/login'); return
            aid, addr = data.get('id', [''])[0], data.get('address', [''])[0]
            conn = sqlite3.connect(DB_PATH); conn.execute("UPDATE addresses SET address_text=? WHERE id=? AND username=?", (addr, aid, user_session['name'])); conn.commit(); conn.close()
            self.redirect('/profile')

        elif self.path == '/cart/qty':
            if not user_session or user_session['role'] == 'admin': self.redirect('/'); return
            pid, change = data.get('product_id', [''])[0], int(data.get('change', ['0'])[0])
            conn = sqlite3.connect(DB_PATH)
            conn.execute('UPDATE carts SET quantity = quantity + ? WHERE product_id = ? AND username = ?', (change, pid, user_session['name']))
            conn.execute('DELETE FROM carts WHERE product_id = ? AND quantity < 1', (pid,))
            conn.commit(); conn.close(); self.redirect('/cart')

        elif self.path == '/admin/add':
            if user_session and user_session['role'] == 'admin':
                n, pr, i, d = data.get('name', [''])[0], data.get('price', ['0'])[0], data.get('img', [''])[0], data.get('desc', [''])[0]
                conn = sqlite3.connect(DB_PATH); conn.execute("INSERT INTO products (name, price, img, description) VALUES (?,?,?,?)", (n, float(pr), i, d)); conn.commit(); conn.close()
            self.redirect('/admin')

        elif self.path == '/cart/add':
            if not user_session or user_session['role'] == 'admin': self.redirect('/'); return
            pid = data.get('product_id', [''])[0]
            conn = sqlite3.connect(DB_PATH)
            existing = conn.execute('SELECT quantity FROM carts WHERE username = ? AND product_id = ?', (user_session['name'], pid)).fetchone()
            if existing: conn.execute('UPDATE carts SET quantity = quantity + 1 WHERE username = ? AND product_id = ?', (user_session['name'], pid))
            else: conn.execute('INSERT INTO carts (username, product_id, quantity) VALUES (?, ?, ?)', (user_session['name'], pid, 1))
            conn.commit(); conn.close(); self.redirect('/cart')

    def send_html(self, content):
        self.send_response(200); self.send_header('Content-type', 'text/html; charset=utf-8'); self.end_headers(); self.wfile.write(content.encode())

    def redirect(self, path):
        self.send_response(302); self.send_header('Location', path); self.end_headers()

if __name__ == "__main__":
    init_db()
    print(f" Running at http://localhost:{PORT}")
    socketserver.TCPServer(("", PORT), ShopHandler).serve_forever()
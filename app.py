"""Aplicación de panadería: frontend Flask, API REST y persistencia SQLite."""
import os
import sqlite3
import uuid
from pathlib import Path

from flask import Flask, g, jsonify, render_template, request
from werkzeug.exceptions import HTTPException


PRODUCTS = [
    (1, 'Pan campesino', 'Masa madre, corteza crujiente y 24 horas de paciencia.', 350, 'Panes', 'hogaza', 'El favorito'),
    (2, 'Croissant de mantequilla', 'Capas doradas de mantequilla. Un clásico que enamora.', 180, 'Bollería', 'croissant', 'Recién horneado'),
    (3, 'Roll de canela', 'Suave por dentro, con canela y un delicado glaseado.', 250, 'Dulces', 'roll', ''),
    (4, 'Baguette artesanal', 'Ligera, dorada y perfecta para compartir en la mesa.', 220, 'Panes', 'baguette', ''),
    (5, 'Galleta de chocolate', 'Chocolate semiamargo y un centro irresistible.', 150, 'Dulces', 'cookie', ''),
    (6, 'Pain au chocolat', 'Masa hojaldrada con un corazón de chocolate.', 240, 'Bollería', 'chocolat', ''),
]


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(
        DATABASE=os.environ.get('DATABASE_PATH', str(Path(app.instance_path) / 'panaderia.sqlite3')),
        MAX_CONTENT_LENGTH=32 * 1024,
    )
    if config:
        app.config.update(config)
    Path(app.config['DATABASE']).resolve().parent.mkdir(parents=True, exist_ok=True)

    def db():
        if 'db' not in g:
            g.db = sqlite3.connect(app.config['DATABASE'], timeout=15)
            g.db.row_factory = sqlite3.Row
            g.db.execute('PRAGMA foreign_keys = ON')
        return g.db

    @app.teardown_appcontext
    def close_db(error=None):
        conn = g.pop('db', None)
        if conn is not None:
            conn.close()

    with app.app_context():
        conn = db()
        conn.execute('PRAGMA journal_mode = WAL')
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL,
                price_cents INTEGER NOT NULL CHECK(price_cents > 0), category TEXT NOT NULL,
                illustration TEXT NOT NULL, badge TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT, reference TEXT NOT NULL UNIQUE,
                customer_name TEXT NOT NULL, phone TEXT NOT NULL, notes TEXT NOT NULL,
                total_cents INTEGER NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL REFERENCES orders(id),
                product_id INTEGER NOT NULL REFERENCES products(id), product_name TEXT NOT NULL,
                quantity INTEGER NOT NULL CHECK(quantity > 0), unit_price_cents INTEGER NOT NULL
            );
        ''')
        conn.executemany('INSERT OR IGNORE INTO products VALUES (?, ?, ?, ?, ?, ?, ?)', PRODUCTS)
        conn.commit()

    @app.get('/')
    def index():
        return render_template('index.html')

    @app.get('/api/health')
    def health():
        db().execute('SELECT 1').fetchone()
        return jsonify(status='ok', database='ok')

    @app.get('/api/products')
    def products():
        return jsonify([dict(row) for row in db().execute('SELECT * FROM products ORDER BY id')])

    @app.post('/api/orders')
    def order():
        data = request.get_json()
        if not isinstance(data, dict):
            return jsonify(error='El pedido debe ser un objeto JSON.'), 400
        name, phone, notes = (data.get(key, '') for key in ('name', 'phone', 'notes'))
        if not isinstance(name, str) or not 2 <= len(name.strip()) <= 80:
            return jsonify(error='Escribe un nombre de entre 2 y 80 caracteres.'), 400
        if not isinstance(phone, str) or not 7 <= len(phone.strip()) <= 25 or not all(c.isascii() and (c.isdigit() or c in '+ ()-') for c in phone) or sum(c.isdigit() for c in phone) < 7:
            return jsonify(error='Escribe un teléfono válido.'), 400
        if not isinstance(notes, str) or len(notes) > 500:
            return jsonify(error='Las indicaciones deben tener hasta 500 caracteres.'), 400
        items = data.get('items')
        if not isinstance(items, list) or not 1 <= len(items) <= 20:
            return jsonify(error='Agrega entre 1 y 20 productos al pedido.'), 400
        lines, seen = [], set()
        for item in items:
            if not isinstance(item, dict) or type(item.get('product_id')) is not int or type(item.get('quantity')) is not int:
                return jsonify(error='Producto o cantidad no válidos.'), 400
            product_id, quantity = item['product_id'], item['quantity']
            if not 1 <= quantity <= 20 or product_id in seen:
                return jsonify(error='Usa entre 1 y 20 unidades por producto, sin duplicados.'), 400
            product = db().execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
            if product is None:
                return jsonify(error='Uno de los productos ya no está disponible.'), 400
            seen.add(product_id)
            lines.append((product_id, product['name'], quantity, product['price_cents']))
        total = sum(line[2] * line[3] for line in lines)
        reference = 'HM-' + uuid.uuid4().hex[:12].upper()
        with db() as conn:
            cursor = conn.execute(
                'INSERT INTO orders (reference, customer_name, phone, notes, total_cents) VALUES (?, ?, ?, ?, ?)',
                (reference, name.strip(), phone.strip(), notes.strip(), total),
            )
            conn.executemany('INSERT INTO order_items (order_id, product_id, product_name, quantity, unit_price_cents) VALUES (?, ?, ?, ?, ?)',
                             [(cursor.lastrowid, *line) for line in lines])
        return jsonify(reference=reference, total_cents=total, message='Pedido registrado para retirar en tienda.'), 201

    @app.errorhandler(HTTPException)
    def http_error(error):
        if request.path.startswith('/api/'):
            return jsonify(error={400: 'JSON no válido.', 413: 'El pedido es demasiado grande.', 415: 'Envía el pedido como application/json.'}.get(error.code, error.description)), error.code
        return error

    @app.after_request
    def security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        return response

    return app


if __name__ == '__main__':
    create_app().run(host='127.0.0.1', port=5000)

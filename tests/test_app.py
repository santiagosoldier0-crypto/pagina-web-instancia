import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from app import create_app


class BakeryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name) / 'test.sqlite3')
        self.app = create_app({'TESTING': True, 'DATABASE': self.path})
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp.cleanup()

    def payload(self):
        return {'name': 'Ana Pérez', 'phone': '0991234567', 'notes': 'Sin bolsa',
                'items': [{'product_id': 1, 'quantity': 2}, {'product_id': 2, 'quantity': 1}]}

    def test_catalog_and_frontend(self):
        self.assertEqual(self.client.get('/').status_code, 200)
        self.assertEqual(len(self.client.get('/api/products').json), 6)
        self.assertEqual(self.client.get('/api/health').json['database'], 'ok')
        for asset in ['/static/app.js', '/static/styles.css']:
            response = self.client.get(asset)
            self.assertEqual(response.status_code, 200)
            response.close()

    def test_prices_come_from_database_and_order_persists(self):
        payload = self.payload()
        payload['total_cents'] = 1
        payload['items'][0]['price_cents'] = 1
        response = self.client.post('/api/orders', json=payload)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json['total_cents'], 880)
        with closing(sqlite3.connect(self.path)) as conn:
            self.assertEqual(conn.execute('SELECT total_cents FROM orders').fetchone()[0], 880)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM order_items').fetchone()[0], 2)
        create_app({'TESTING': True, 'DATABASE': self.path})
        with closing(sqlite3.connect(self.path)) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM orders').fetchone()[0], 1)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM products').fetchone()[0], 6)

    def test_invalid_items_never_create_orders(self):
        for items in [[], [None], [{'product_id': 999, 'quantity': 1}],
                      [{'product_id': 1, 'quantity': -1}], [{'product_id': 1, 'quantity': True}],
                      [{'product_id': 1, 'quantity': 21}],
                      [{'product_id': 1, 'quantity': 1}] * 2]:
            with self.subTest(items=items):
                data = self.payload()
                data['items'] = items
                self.assertEqual(self.client.post('/api/orders', json=data).status_code, 400)
        with closing(sqlite3.connect(self.path)) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM orders').fetchone()[0], 0)

    def test_invalid_customer_and_json(self):
        for key, value in [('name', ''), ('phone', 'abc1234'), ('notes', 'a' * 501)]:
            data = self.payload()
            data[key] = value
            self.assertEqual(self.client.post('/api/orders', json=data).status_code, 400)
        self.assertEqual(self.client.post('/api/orders', json=[]).status_code, 400)
        self.assertEqual(self.client.post('/api/orders', data='{', content_type='application/json').status_code, 400)
        self.assertEqual(self.client.post('/api/orders', data='x').status_code, 415)
        self.assertEqual(self.client.post('/api/orders', data='x' * 40000, content_type='application/json').status_code, 413)


if __name__ == '__main__':
    unittest.main()

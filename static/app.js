'use strict';
const money = cents => new Intl.NumberFormat('es-EC', { style: 'currency', currency: 'USD' }).format(cents / 100);
const productsEl = document.querySelector('#products');
const dialog = document.querySelector('#cart-dialog');
const form = document.querySelector('#checkout');
const message = document.querySelector('#checkout-message');
let products = [];
let cart = {};
let submitting = false;
try {
  const saved = JSON.parse(localStorage.getItem('horno-cart') || '{}');
  if (saved && typeof saved === 'object' && !Array.isArray(saved)) {
    for (const [id, qty] of Object.entries(saved)) {
      if (/^\d+$/.test(id) && Number.isInteger(qty) && qty > 0 && qty <= 20) cart[id] = qty;
    }
  }
} catch { /* El almacenamiento local es opcional. */ }
let toastTimer;
function toast(text) {
  const el = document.querySelector('#toast');
  el.textContent = text;
  el.classList.add('visible');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('visible'), 2600);
}
function saveCart() {
  try { localStorage.setItem('horno-cart', JSON.stringify(cart)); } catch { /* Sigue en memoria. */ }
}
function renderCart() {
  saveCart();
  const items = products.filter(p => cart[p.id]);
  document.querySelector('#cart-count').textContent = items.reduce((n, p) => n + cart[p.id], 0);
  const container = document.querySelector('#cart-items');
  container.replaceChildren();
  if (!items.length) container.textContent = 'Tu bolsa espera algo rico. Explora el menú y elige tus favoritos.';
  for (const p of items) {
    const row = document.createElement('div');
    row.className = 'cart-row';
    const info = document.createElement('div');
    const name = document.createElement('strong');
    name.textContent = p.name;
    const price = document.createElement('small');
    price.textContent = money(p.price_cents * cart[p.id]);
    info.append(name, price);
    const controls = document.createElement('div');
    controls.className = 'quantity';
    for (const [label, delta] of [['−', -1], ['+', 1]]) {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = label;
      button.setAttribute('aria-label', `${delta < 0 ? 'Quitar' : 'Agregar'} una unidad de ${p.name}`);
      button.disabled = submitting || (delta > 0 && cart[p.id] >= 20);
      button.onclick = () => { cart[p.id] += delta; if (!cart[p.id]) delete cart[p.id]; message.textContent = ''; renderCart(); };
      controls.append(button);
      if (delta < 0) { const count = document.createElement('span'); count.textContent = cart[p.id]; controls.append(count); }
    }
    row.append(info, controls);
    container.append(row);
  }
  document.querySelector('#cart-total').textContent = money(items.reduce((n, p) => n + p.price_cents * cart[p.id], 0));
  form.querySelector('[type="submit"]').disabled = submitting || !items.length;
}
function renderProducts(category = 'Todos') {
  productsEl.replaceChildren();
  for (const p of products.filter(p => category === 'Todos' || p.category === category)) {
    const card = document.createElement('article');
    card.className = 'product';
    // El catálogo proviene de nuestra BD; todo texto se inserta como textContent.
    const art = document.createElement('div');
    art.className = `product-art art-${p.illustration}`;
    art.setAttribute('aria-hidden', 'true');
    const bread = document.createElement('div');
    bread.className = `pastry ${p.illustration}`;
    for (let i = 0; i < 3; i++) bread.append(document.createElement('span'));
    art.append(bread);
    if (p.badge) { const badge = document.createElement('span'); badge.className = 'badge'; badge.textContent = p.badge; art.append(badge); }
    const heading = document.createElement('h3'); heading.textContent = p.name;
    const description = document.createElement('p'); description.textContent = p.description;
    const bottom = document.createElement('div'); bottom.className = 'product-bottom';
    const price = document.createElement('strong'); price.textContent = money(p.price_cents);
    const add = document.createElement('button'); add.textContent = '+'; add.className = 'add-button';
    add.setAttribute('aria-label', `Agregar ${p.name} al pedido`);
    add.onclick = () => {
      if (submitting) return toast('Espera a que termine de guardarse tu pedido.');
      if ((cart[p.id] || 0) >= 20) return toast('Máximo 20 unidades por producto.');
      cart[p.id] = (cart[p.id] || 0) + 1;
      message.textContent = '';
      renderCart(); toast(`${p.name} agregado a tu pedido`);
    };
    bottom.append(price, add); card.append(art, heading, description, bottom); productsEl.append(card);
  }
}
async function loadProducts() {
  try {
    const response = await fetch('/api/products');
    if (!response.ok) throw new Error();
    products = await response.json();
    for (const id of Object.keys(cart)) if (!products.some(p => String(p.id) === id)) delete cart[id];
    renderProducts(document.querySelector('.filters .active').dataset.category); renderCart();
  } catch {
    productsEl.textContent = 'No pudimos cargar el menú. ';
    const retry = document.createElement('button'); retry.className = 'retry-button'; retry.textContent = 'Volver a intentar'; retry.onclick = loadProducts; productsEl.append(retry);
  }
}
document.querySelectorAll('[data-category]').forEach(button => button.onclick = () => {
  document.querySelectorAll('[data-category]').forEach(b => { b.classList.toggle('active', b === button); b.setAttribute('aria-pressed', String(b === button)); });
  renderProducts(button.dataset.category);
});
document.querySelector('#open-cart').onclick = () => { renderCart(); dialog.showModal(); };
document.querySelector('#close-cart').onclick = () => dialog.close();
dialog.addEventListener('click', event => { if (event.target === dialog) { const r = dialog.getBoundingClientRect(); if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) dialog.close(); } });
form.addEventListener('submit', async event => {
  event.preventDefault();
  if (submitting) return;
  submitting = true;
  renderCart();
  const button = form.querySelector('[type="submit"]');
  button.disabled = true; button.textContent = 'Guardando pedido…'; message.textContent = '';
  const fields = new FormData(form);
  try {
    const response = await fetch('/api/orders', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: fields.get('name'), phone: fields.get('phone'), notes: fields.get('notes'), items: Object.entries(cart).map(([id, quantity]) => ({ product_id: Number(id), quantity })) }) });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'No pudimos guardar tu pedido.');
    cart = {}; renderCart(); form.reset();
    message.textContent = `¡Gracias! Tu pedido ${result.reference} está registrado. Total: ${money(result.total_cents)}. Retíralo en tienda dentro del horario de atención. Guarda este número.`;
  } catch (error) { message.textContent = error.message === 'Failed to fetch' ? 'No hay conexión. Revisa tu conexión antes de intentar de nuevo.' : error.message; }
  finally { submitting = false; renderCart(); button.textContent = 'Confirmar pedido ↗'; }
});
loadProducts();

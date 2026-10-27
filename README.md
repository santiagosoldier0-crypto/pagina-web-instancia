# Horno & Miga — Panadería artesanal

Aplicación académica completa: **frontend HTML/CSS/JavaScript**, **backend Python con Flask** y **base de datos SQLite**. Incluye catálogo, filtros, carrito, formulario y registro persistente de pedidos. Precios en dólares (USD).

El carrito se conserva en el navegador; los pedidos y sus productos se guardan en el servidor. Los panes del catálogo tienen ilustraciones CSS y la interfaz no depende de servicios de imágenes ni de fuentes externas.

## Arquitectura

```text
Navegador (HTML + CSS + JavaScript)
            | fetch /api/products y /api/orders
            v
Nginx :80 → Gunicorn 127.0.0.1:8000 → Flask → SQLite
              (en AWS)                        (archivo persistente)
```

SQLite es una base de datos relacional real. No necesita servidor independiente y es adecuada para esta demostración en una sola instancia. Si tu materia exige MySQL/PostgreSQL o una base de datos en otra instancia, esta implementación debe adaptarse a ese requisito.

## 1. Ejecutar en Windows

Requiere Python 3.10 o superior y Git. Instala Python desde <https://www.python.org/downloads/> y marca **Add Python to PATH**. Si `python` abre Microsoft Store, revisa los alias de ejecución de Windows o usa `py`.

En PowerShell, dentro de esta carpeta:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

Abre **http://127.0.0.1:5000**. Detén el servidor con `Ctrl+C`. No necesitas activar el entorno virtual ni cambiar la política de ejecución de PowerShell.

Alternativa con servidor WSGI en Windows:

```powershell
.\.venv\Scripts\waitress-serve.exe --listen=127.0.0.1:5000 wsgi:app
```

En Linux/macOS, crea el entorno con `python3 -m venv .venv`, instala con `.venv/bin/python -m pip install -r requirements.txt` y ejecuta `.venv/bin/python app.py`.

La base de datos y los seis productos iniciales se crean automáticamente al iniciar. Archivo local: `instance/panaderia.sqlite3`. Reiniciar la aplicación conserva los pedidos.

## 2. Subir a GitHub

Repositorio del proyecto: https://github.com/santiagosoldier0-crypto/pagina-web-instancia. Estos comandos documentan la preparación inicial desde esta carpeta. Si el remoto ya está configurado, omite `git remote add origin`:

```powershell
git init
git add .
git commit -m "Crear aplicación de panadería con Flask y SQLite"
git branch -M main
git remote add origin https://github.com/santiagosoldier0-crypto/pagina-web-instancia.git
git push -u origin main
```

Git puede solicitar que inicies sesión en GitHub mediante el navegador. Si solicita identidad antes del commit, configura `git config user.name "Tu nombre"` y `git config user.email "tu-correo"` para este repositorio. Si ya existe un remoto, consulta `git remote -v` antes de cambiarlo.

`.gitignore` excluye la base de datos, entornos virtuales y archivos de configuración privados. No subas llaves `.pem`, credenciales de AWS ni datos de clientes.

## 3. Preparar la instancia académica de AWS

Enciende tu laboratorio académico antes de usar EC2. Usa una instancia dedicada con **Ubuntu Server 22.04/24.04** o **Amazon Linux 2023**, según lo autorizado en tu curso. No se necesita RDS, Docker ni claves de API de AWS dentro de la aplicación.

La instancia necesita IP pública, salida a Internet y estas reglas de entrada en su **grupo de seguridad**:

| Tipo | Puerto | Origen |
| --- | --- | --- |
| SSH | 22 | Tu IP pública actual (`/32`) |
| HTTP | 80 | `0.0.0.0/0` para poder mostrar la web |

No es necesario abrir 5000, 8000 ni puertos de base de datos. Si Ubuntu tiene UFW activo, permite OpenSSH y `80/tcp` antes de continuar. Referencia: [reglas de grupos de seguridad de EC2](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/security-group-rules-reference.html).

Conecta mediante **EC2 Instance Connect** desde la consola, si tu laboratorio lo permite, o mediante SSH desde PowerShell:

```powershell
ssh -i "C:\ruta\llave.pem" ubuntu@IP_PUBLICA
```

En Amazon Linux el usuario normalmente es `ec2-user` en lugar de `ubuntu`. Usa la IP y la llave de tu instancia; no compartas la llave privada.

## 4. Clonar e instalar en AWS

Ejecuta estos comandos **dentro de la terminal de la instancia**.

Ubuntu:

```bash
sudo apt-get update
sudo apt-get install -y git
```

Amazon Linux 2023:

```bash
sudo dnf install -y git
```

Después, para ambos sistemas:

```bash
git clone https://github.com/santiagosoldier0-crypto/pagina-web-instancia.git
cd pagina-web-instancia
sudo bash deploy/setup.sh
```

El script instala dependencias, copia la aplicación a `/opt/panaderia`, crea un usuario de servicio, configura Gunicorn con systemd y Nginx, y comprueba la API. Está pensado para una instancia dedicada: configura HTTP y deshabilita el enlace del sitio de bienvenida de Ubuntu. La aplicación arranca automáticamente al reiniciar la instancia.

Si el repositorio es privado, autentícate con el mecanismo de GitHub autorizado por tu curso. No incrustes tokens en la URL del repositorio ni en el código.

Abre en tu navegador:

```text
http://IP_PUBLICA
```

Usa `http://` explícitamente: este despliegue académico no configura certificado HTTPS. Para una tienda real se necesitan dominio, HTTPS y medidas operativas adicionales. Utiliza datos ficticios en esta demostración.

## 5. Verificar y demostrar

1. Abre el catálogo y cambia entre Panes, Bollería y Dulces.
2. Agrega productos, cambia cantidades y confirma un pedido con datos ficticios.
3. Guarda la referencia `HM-...` que aparece al confirmar.
4. Desde la instancia comprueba la API y el estado del servicio:

```bash
curl http://127.0.0.1/api/health
sudo systemctl status panaderia --no-pager
sudo systemctl status nginx --no-pager
```

Para ver que el pedido se guardó realmente en SQLite:

```bash
sudo /opt/panaderia/.venv/bin/python -c "import sqlite3; c=sqlite3.connect('/opt/panaderia/instance/panaderia.sqlite3'); print(c.execute('SELECT reference, total_cents, created_at FROM orders ORDER BY id DESC LIMIT 10').fetchall())"
```

Los totales están en centavos: `880` equivale a `$8.80`. La tabla `order_items` conserva las unidades y el precio de cada producto al momento del pedido.

Prueba la persistencia con `sudo systemctl restart panaderia` y vuelve a consultar la base. El archivo permanece en `/opt/panaderia/instance/panaderia.sqlite3`. Si el laboratorio elimina la instancia o su disco, también se perderán sus datos; cerrar el laboratorio puede cambiar la IP pública en el siguiente inicio.

## Actualizar después de un cambio

En tu computadora: `git add .`, `git commit -m "Descripción del cambio"` y `git push`.

En la instancia, dentro del clon de tu carpeta personal:

```bash
git pull --ff-only
sudo bash deploy/setup.sh
```

El instalador conserva la base de datos. El catálogo inicial se inserta solo cuando falta un producto; cambiar un precio de los registros existentes requiere actualizar la base explícitamente.

## Pruebas automatizadas

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

En Linux: `.venv/bin/python -m unittest discover -s tests -v`. GitHub Actions también ejecuta estas pruebas en cada push o pull request. Comprueban el catálogo, archivos del frontend, persistencia, cálculo del total en servidor y rechazo de pedidos inválidos. Usan una base temporal independiente.

## API y datos

| Método | Ruta | Función |
| --- | --- | --- |
| GET | `/` | Página de la panadería |
| GET | `/api/products` | Catálogo leído de la base de datos |
| POST | `/api/orders` | Validar y guardar pedido y detalle en una transacción |
| GET | `/api/health` | Comprobar servicio y conexión SQLite |

Ejemplo de cuerpo para crear un pedido:

```json
{
  "name": "Cliente de prueba",
  "phone": "0991234567",
  "notes": "Retiro en tienda",
  "items": [{"product_id": 1, "quantity": 2}]
}
```

El servidor responde con referencia y total. Las consultas SQL usan parámetros y los importes se calculan en centavos desde los precios de la base. No hay un endpoint público para listar datos de clientes. No incluye pagos, cuentas de usuarios, inventario ni panel administrativo.

Tablas: `products` (catálogo), `orders` (cliente, referencia, total y fecha UTC) y `order_items` (relación entre pedido y productos). La relación es `orders 1 → N order_items` y `products 1 → N order_items`.

## Si algo falla

- **La web no abre:** confirma que el laboratorio y la instancia estén encendidos, usa la IP pública actual y revisa puerto 80, grupo de seguridad y firewall del sistema.
- **502 Bad Gateway:** revisa `sudo journalctl -u panaderia -n 50 --no-pager` y `sudo systemctl status panaderia`.
- **Nginx no inicia:** ejecuta `sudo nginx -t` y revisa si otra aplicación ocupa el puerto 80.
- **Funciona dentro de EC2 pero no en tu computadora:** prueba `curl http://127.0.0.1/api/health` en EC2; si responde, revisa red, IP y reglas de entrada.
- **GitHub rechaza el push:** comprueba el remoto y la autenticación. Una contraseña normal de GitHub no sirve como token de Git.

## Archivos principales

```text
app.py                    Backend, validación y creación de tablas
wsgi.py                   Entrada para Gunicorn / Waitress
templates/index.html      Frontend
static/styles.css         Diseño responsive e ilustraciones
static/app.js             Catálogo, filtros, carrito y llamadas a la API
requirements.txt          Dependencias
tests/test_app.py         Pruebas con base temporal
deploy/setup.sh           Instalación en EC2
.github/workflows/tests.yml  Pruebas en GitHub
```

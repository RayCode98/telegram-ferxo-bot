# FreXo Telegram Bot

MVP funcional de chat aleatorio anónimo para Telegram con:

- Registro 18+ y perfil.
- Preferencia de género.
- Búsqueda global.
- Búsqueda por cercanía con ubicación voluntaria.
- Emparejamiento compatible.
- Relay anónimo de mensajes con `copyMessage`.
- Finalizar / siguiente.
- Likes y Super Interés.
- Bloqueos y reportes.
- PostgreSQL para datos persistentes.
- Redis para cola, sesión de chat y límites.
- Monetización con Telegram Stars (`XTR`):
  - FreXo Premium: 199 Stars / 30 días.
  - Boost 30 min: 25 Stars.
  - Super Interés: 10 Stars.
  - Reconectar: 15 Stars.
- `/paysupport`.

## 1. Crear el bot

Crea el bot con `@BotFather` y copia el token.

## 2. Configurar

```bash
cp .env.example .env
nano .env
```

Configura al menos:

```env
BOT_TOKEN=...
SUPPORT_USERNAME=@TuSoporte
```

## 3. Levantar con Docker

```bash
docker compose up -d --build
```

Ver logs:

```bash
docker compose logs -f bot
```

## 4. Desarrollo local

Necesitas PostgreSQL y Redis activos.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

En Windows:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Arquitectura

```text
app/
├── handlers/       # Updates de Telegram
├── services/       # Matchmaking, relay y pagos
├── config.py
├── database.py
├── keyboards.py
├── models.py
├── redis_client.py
├── repositories.py
└── states.py
```

## Seguridad

El bot no entrega automáticamente usernames o IDs del compañero.

La ubicación compartida se usa sólo para calcular distancia. No se reenvía al compañero.

Bloqueos y reportes son gratuitos. Ningún producto Premium puede evitar un bloqueo.

## Pendientes recomendados para la siguiente fase

- Edición completa de perfil.
- Rango de edad y radio de distancia desde UI.
- Filtro por país / Travel Mode.
- Reconexión real usando historial elegible.
- Vista de personas que dieron Like para Premium.
- Panel administrativo.
- Moderación avanzada y antiflood.
- Referral system.
- Alembic para migraciones versionadas.
- Webhook + Nginx cuando se requiera escalar.
- Métricas de conversión, retención e ingresos.


## v1.2 — Perfil y preferencias avanzadas

Incluye:

- Edición de alias.
- Descripción/Bio de hasta 300 caracteres.
- Foto de perfil mediante Telegram `file_id`.
- Actualización de ubicación.
- Vista del perfil de la pareja durante una conversación.
- Distancia aproximada sin revelar coordenadas.
- Cambio de preferencia de género.
- Filtro Premium de rango de edad.
- Filtro Premium de radio: 5, 10, 25, 50 o 100 km.
- El usuario gratuito conserva búsqueda cercana hasta 100 km.

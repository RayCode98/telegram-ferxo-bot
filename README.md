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


## v1.3 — Conexiones, Likes y Reconexión

- Alias y edad visibles para todos como datos básicos de confianza.
- Usuario gratuito: perfil básico (alias, edad y género).
- Premium: foto, bio y distancia aproximada desde el inicio.
- `👀 Conocer más`: si ambos aceptan, se desbloquea el perfil completo incluso sin Premium.
- `📲 Compartir Telegram`: sólo se revela después de doble consentimiento.
- `❤️ Likes recibidos`: gratis ve la cantidad; Premium ve quiénes son.
- Premium puede devolver interés desde la lista de Likes.
- Reconexión real usando créditos comprados con Stars.
- La reconexión requiere aceptación del otro usuario.
- Nunca se permite reconectar tras bloqueo/reporte.
- Solicitudes de reconexión expiran en 24 horas.


## v1.4 — Seguridad, moderación y formato de conversación

### Diferenciación visual

Los mensajes retransmitidos desde otra persona muestran:

```text
👤 Tu conexión

Hola, ¿cómo estás?
```

Los avisos internos usan el estilo:

```text
🤖 FreXo

Conversación terminada.
```

Para fotografías, videos, documentos y contenido con caption, FreXo intenta integrar
la etiqueta `👤 Tu conexión` en el propio caption. Para stickers, video notas y
contenidos sin caption, envía una cabecera inmediatamente antes.

### Seguridad

- Antiflood de mensajes.
- Cooldown progresivo por spam.
- Límite de uso excesivo de `Siguiente`.
- Límite de búsquedas por ráfaga.
- Límite diario de reportes.
- Restricciones temporales y permanentes.
- Registro de acciones administrativas.
- Los baneos interrumpen el chat activo.
- Opción `PROTECT_RELAYED_CONTENT=true`.

### Administración

Configura `ADMIN_IDS` en `.env` y utiliza:

```text
/admin
/userinfo TELEGRAM_ID
/ban TELEGRAM_ID 24 motivo
/ban TELEGRAM_ID perm motivo
/unban TELEGRAM_ID
```

El panel incluye estadísticas y revisión de reportes.


## v1.5 — Crecimiento y monetización avanzada

### Referidos
Cada usuario obtiene un enlace:

```text
https://t.me/TU_BOT?start=ref_CODIGO
```

El referido no se considera válido por iniciar el bot. Se califica cuando logra su
primer match, reduciendo abuso con cuentas vacías.

Recompensas:

- Cada referido calificado: 1 Super Interés.
- 3 calificados: 1 Travel Pass + 1 Spotlight.
- 5 calificados: 1 Boost gratis + 3 Super Intereses.

### Travel Mode
- Producto: 15 Stars.
- Añade 1 Travel Pass.
- El usuario selecciona un país.
- Matchmaking filtra candidatos del país objetivo durante 24 h.
- El país de origen se configura desde `🌎 Explorar`.

### Spotlight
- Producto: 50 Stars.
- Crédito activable cuando el usuario quiera.
- Duración: 3 horas.
- Añade +175 puntos a la puntuación de matchmaking.

### Boost
- 30 minutos: 25 Stars.
- 60 minutos: 45 Stars.
- Los Boost de pago se activan inmediatamente.
- Los Boost ganados por referidos quedan como crédito activable.

### Regalos virtuales
Durante un chat:

- Rosa: 5 Stars.
- Café: 10 Stars.
- Flores: 25 Stars.
- Diamante: 100 Stars.

Los regalos no transfieren dinero al receptor y no revelan su Telegram.
Quedan registrados como objetos sociales en el perfil FreXo.

### Analítica
El panel `/admin` agrega `📈 Conversión` con:

- nuevos usuarios 30 días;
- matches;
- compras;
- compradores únicos;
- Stars cobradas;
- conversión usuario → comprador;
- ingresos por producto.


### País durante onboarding

Los usuarios nuevos seleccionan su país antes de la ubicación opcional. Esto permite
que Travel Mode tenga suficientes perfiles clasificables desde el comienzo.
Los usuarios existentes pueden definirlo desde `🌎 Explorar`.


## v1.6 — Retención y UX

### Navegación
- Paneles principales incluyen `🏠 Inicio`.
- Subpaneles incluyen `⬅️ Atrás`.
- Volver a inicio limpia estados FSM incompletos.
- Si existe una conversación activa, `Inicio` no la oculta: FreXo vuelve a
  mostrar el panel de conversación.

### Panel persistente de conversación
Al comenzar un match, FreXo crea:

```text
🧭 CONVERSACIÓN ACTIVA

👤 Andrea
🎂 24 años
🚻 Mujer
📍 A menos de 10 km

📌 Este panel queda fijado arriba.
```

- Se fija automáticamente en el chat privado.
- Se actualiza si ambos aceptan `Conocer más`.
- Se desfija al terminar, bloquear o reportar.
- Puede recuperarse con `🧭 Panel de chat`.
- No depende de desplazarse entre cientos de mensajes.

### Teclado de chat persistente
Durante una conversación, el teclado inferior cambia a:

```text
🧭 Panel de chat     👤 Mi conexión
❤️ Me interesa       🎁 Regalo
🔄 Siguiente         ❌ Terminar
```

Al terminar, vuelve automáticamente al menú principal.

### Recompensas diarias
En `🎁 Recompensas` aparece una racha diaria.

Reglas:
- Reclamable cada 20 horas.
- Hasta 48 horas para conservar la racha.
- Ciclo de 7 recompensas:
  1. Super Interés
  2. Super Interés
  3. Boost 30 min
  4. 2 Super Intereses
  5. Travel Pass
  6. 2 Super Intereses
  7. Spotlight 3 h

Nueva tabla: `retention_profiles`.

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

## v1.7 — Historial, favoritos, intereses y compatibilidad

### Panel inferior paginado
Durante una conversación el teclado persistente usa dos páginas.

Página 1:

```text
🧭 Panel de chat     👤 Mi conexión
❤️ Me interesa       👀 Conocer más
🔄 Siguiente         ❌ Terminar
➡️ Más opciones
```

Página 2:

```text
💘 Super Interés     📲 Compartir Telegram
🎁 Regalo            ⭐ Guardar favorito
🚫 Bloquear          🚨 Reportar
🔄 Siguiente         ❌ Terminar
⬅️ Acciones principales
```

`Siguiente` y `Terminar` están disponibles en ambas páginas para no ocultar
acciones críticas de la conversación.

### Historial
- Gratis: últimas 5 conexiones.
- Premium: últimas 20 conexiones.
- Muestra alias, edad, fecha, motivo de cierre y actividad reciente dentro de FreXo.
- Los bloqueos/reportes siguen impidiendo reconexiones aunque aparezcan como historial.

### Favoritos
- La conexión actual puede guardarse como favorita desde la página 2 del teclado.
- Existe un panel `⭐ Favoritos` en el menú principal.
- Guardar un favorito es privado y no notifica a la otra persona.

### Intereses y hobbies
El usuario puede elegir hasta 6 intereses desde `👤 Mi perfil → 🎯 Mis intereses`.
También se sugieren al terminar el onboarding.

Catálogo inicial:
- Música, viajes, videojuegos, deportes, cine/series, lectura.
- Fitness, comida, naturaleza, tecnología, mascotas, arte.
- Baile, fotografía, negocios e idiomas.

Los intereses:
- aparecen en el perfil;
- añaden puntos al matchmaking;
- muestran intereses compartidos;
- generan un rompehielo en el panel fijado de conversación.

### Compatibilidad FreXo
FreXo muestra un porcentaje aproximado propio combinando:
- preferencias compatibles;
- diferencia de edad;
- distancia cuando existe ubicación;
- intereses en común.

No representa una garantía de afinidad; es únicamente un indicador del algoritmo de FreXo.

### Actividad reciente
La Bot API no expone al bot el `last seen`/online real de la cuenta de Telegram.
Por eso FreXo sólo muestra actividad dentro del propio bot:

```text
🟢 Activo recientemente en FreXo
⚪ Sin actividad reciente en FreXo
⚪ Actividad oculta
```

La preferencia puede apagarse desde `⚙️ Preferencias`.

### Notificaciones inteligentes
Cuando una persona compatible comienza a buscar y no encuentra match inmediatamente,
FreXo puede avisar de forma oportunista a usuarios compatibles que tengan esta función activa.

Protecciones:
- máximo 2 avisos por día por destinatario;
- deduplicación entre la misma pareja durante 6 horas;
- no se avisa a personas en conversación o ya buscando;
- score mínimo de compatibilidad;
- botón para desactivar los avisos inmediatamente.

### Nuevas tablas
- `user_interests`
- `favorites`
- `experience_preferences`

Estas son tablas nuevas, por lo que el `create_all()` actual puede crearlas sin borrar
los usuarios, pagos, conversaciones ni información existente.


## v1.8 — Calidad de conversación y retención avanzada

### Corrección crítica al cerrar chats
La otra persona recibe una notificación explícita antes del menú:

```text
🤖 FreXo

👋 Tu conexión terminó la conversación.

Ya puedes buscar otra persona cuando quieras.
```

`Siguiente`, bloqueos, reportes e inactividad tienen mensajes diferenciados.

### Feedback después de conversaciones
Tras `Terminar`, `Siguiente` o cierre por inactividad:

```text
👍 Buena   😐 Normal   👎 Mala
```

El feedback sirve para analítica de calidad. Una valoración mala aislada no sanciona.

### Calidad de mensajes
Nueva tabla `conversation_quality`:
- mensajes enviados por cada integrante;
- último remitente;
- cantidad de mensajes consecutivos;
- último mensaje;
- recordatorio de inactividad.

Si alguien envía demasiados mensajes seguidos sin respuesta, FreXo muestra
un recordatorio suave. No genera una sanción automática.

### Ghosting / abandono
- Después de `GHOSTING_NUDGE_MINUTES` (15 por defecto), se recuerda al último
  remitente que dé tiempo a la conexión.
- Después de `CONVERSATION_IDLE_CLOSE_HOURS` (24 h por defecto), una conversación
  abandonada se cierra automáticamente y libera ambos usuarios.
- El monitor se ejecuta dentro del proceso del bot cada 5 minutos.

### Sugerencias de conversación
Botón persistente `💡 Sugerencia`.
Si existen intereses compartidos, FreXo genera una pregunta relacionada.
Si no, utiliza rompehielos generales.

### Reconexión selectiva desde Favoritos
Cada favorito ofrece `↩️ Solicitar reconexión`.
Consume un crédito de Reconexión y siempre requiere aprobación de la otra persona.

### Misiones semanales
- 3 matches → 💘 2 Super Intereses
- 25 mensajes → 🚀 Boost 30 min
- 3 recompensas diarias → 🌎 Travel Pass
- Reclamar las tres → 🔥 Spotlight 3 h

### Estadísticas personales
Desde `👤 Mi perfil → 📊 Mis estadísticas`:
- conexiones;
- mensajes enviados (el contador técnico comenzó a persistirse en v1.8);
- intereses enviados/recibidos;
- favoritos;
- regalos;
- rachas.

Nuevas tablas:
- `conversation_quality`
- `conversation_feedback`
- `weekly_progress`


## v1.9 — Production Ready

FreXo v1.9 congela el desarrollo de funciones grandes y endurece operación:

- Alembic 1.19.1; el bot ya no crea/modifica esquema con `create_all()` al arrancar.
- Baseline de adopción para instalaciones v1.8.x existentes.
- `entrypoint.sh` ejecuta `alembic upgrade head` antes del bot.
- PostgreSQL → Redis recovery para conversaciones activas tras reinicios.
- Cola efímera de matchmaking se limpia tras reinicio para evitar búsquedas fantasma.
- Endpoint local `/health` con PostgreSQL + Redis + readiness.
- Healthchecks Docker y rotación de logs.
- Logs JSON a stdout.
- Backups automáticos diarios, semanales y mensuales.
- Admin financiero de Telegram Stars: balance real y últimos movimientos.
- Reembolso auditado mediante `/refund CHARGE_ID motivo`.
- Estado de suscripción Premium con cancelar/reactivar renovación.
- Manejo del evento `subscription` de Bot API 10.2.
- Centro de ayuda, privacidad, términos, normas y eliminación/anominización de cuenta.
- `production_check.py` y `load_test_redis.py`.

### IMPORTANTE: actualizar una instalación existente

Tu volumen PostgreSQL ya tiene una contraseña real. Cambiar `POSTGRES_PASSWORD` en
Docker Compose **no cambia** la contraseña dentro de una base ya inicializada.
En la primera actualización conserva las credenciales actuales.

Ejemplo para una instalación que todavía usa `frexo/frexo`:

```env
POSTGRES_DB=frexo
POSTGRES_USER=frexo
POSTGRES_PASSWORD=frexo
DATABASE_URL=postgresql+asyncpg://frexo:frexo@postgres:5432/frexo
```

Luego puedes rotarla de forma controlada.

### Actualización

```bash
cd /opt/frexo/frexo_telegram_bot

docker compose exec -T postgres \
  pg_dump -U frexo frexo > backup_antes_v1.9.sql

# reemplazar archivos conservando .env

docker compose up -d --build
```

El bot aplica automáticamente:

```bash
alembic upgrade head
```

Comprueba:

```bash
docker compose ps
docker compose logs --tail=200 bot
curl http://127.0.0.1:8080/health
docker compose exec bot alembic current
docker compose exec bot python scripts/production_check.py
```

### Rotar la contraseña PostgreSQL después de comprobar v1.9

Genera una contraseña:

```bash
openssl rand -hex 32
```

Cámbiala dentro de PostgreSQL (sustituye NUEVA_PASSWORD):

```bash
docker compose exec postgres \
  psql -U frexo -d frexo \
  -c "ALTER USER frexo WITH PASSWORD 'NUEVA_PASSWORD';"
```

Actualiza simultáneamente `.env`:

```env
POSTGRES_PASSWORD=NUEVA_PASSWORD
DATABASE_URL=postgresql+asyncpg://frexo:NUEVA_PASSWORD@postgres:5432/frexo
```

Después:

```bash
docker compose up -d --force-recreate bot backup
```

### Backups

El servicio `backup` guarda en `./backups`:

- diarios: 7 días;
- semanales: ~5 semanas;
- mensuales: ~3 meses.

Comprueba:

```bash
find backups -type f -name '*.sql.gz' -ls
```

Ejecuta uno manual:

```bash
docker compose run --rm backup sh /scripts/backup_postgres.sh
```

Prueba restauración siempre en una base separada antes de confiar en el plan.

### Finanzas

En `/admin` abre `💰 Finanzas`. Consulta `getMyStarBalance` y
`getStarTransactions` directamente contra Telegram.

Reembolso:

```text
/refund TELEGRAM_PAYMENT_CHARGE_ID motivo
```

### Legal

Los textos legales incluidos son una base funcional para la beta y no sustituyen
asesoría jurídica adaptada a los territorios donde FreXo se comercialice.


## v1.9.1 — Reporte diario administrativo

`/admin` incluye ahora `📅 Reporte de hoy`.

El reporte utiliza la zona horaria definida por:

```env
ADMIN_REPORT_TIMEZONE=America/Mexico_City
```

Muestra:

- usuarios nuevos;
- activos del día y últimos 15 minutos;
- búsquedas iniciadas;
- usuarios buscando actualmente;
- matches;
- mensajes;
- conversaciones activas;
- Likes/intereses;
- valoraciones de conversación;
- bloqueos y reportes;
- compras y compradores;
- conversión de activos a compradores;
- Premium vendidos y Premium activos;
- Stars brutas, reembolsos y Stars netas.

Las búsquedas se registran desde v1.9.1 mediante el evento
`analytics_events.event_name = "search_started"`.

También existe el comando administrativo:

```text
/daily
```

para abrir el mismo reporte directamente.

# Changelog

## v1.1 - Telegram Stars subscription fix

- FreXo Premium now uses `createInvoiceLink` for recurrent Stars subscriptions.
- `subscription_period=2592000` is no longer passed to `sendInvoice`.
- One-time purchases continue using `sendInvoice`.
- Existing pre-checkout and successful payment validation remains intact.


## v1.2 - Perfil y filtros avanzados

- Perfil editable con alias, bio y fotografía.
- Tarjeta de perfil dentro del chat anónimo.
- Distancia aproximada entre usuarios.
- Preferencias editables.
- Rango de edad Premium.
- Radio de distancia Premium.
- Se mantiene el anonimato del Telegram real.


## v1.3 - Conexiones sociales

- Likes recibidos y lista Premium.
- Consentimiento mutuo para perfil ampliado.
- Consentimiento mutuo para compartir Telegram.
- Reconexión consumible implementada.
- Nuevas tablas `connection_consents` y `reconnect_requests`.
- Perfil básico gratis / perfil ampliado Premium.


## v1.4 - Seguridad y moderación

- Los mensajes de usuarios se etiquetan como `👤 Tu conexión`.
- Avisos de conversación etiquetados como `🤖 FreXo`.
- Formato HTML conservado en mensajes de texto.
- Captions etiquetados en fotografías, videos, audios y documentos.
- Antiflood de chat y cooldown progresivo.
- Rate limit para búsquedas, `Siguiente` y reportes.
- Restricciones temporales/permanentes.
- Panel `/admin`.
- Estadísticas administrativas.
- Revisión de reportes con ban 24h o permanente.
- Nuevas tablas `user_restrictions`, `moderation_actions`, `report_reviews`.

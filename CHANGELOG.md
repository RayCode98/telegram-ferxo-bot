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


## v1.5 - Growth + monetización

- Sistema de referidos con deep links.
- Calificación del referido en el primer match.
- Recompensas por 1, 3 y 5 referidos.
- Travel Mode 24 horas.
- País de origen para matchmaking internacional.
- Spotlight de 3 horas.
- Boost de 60 minutos.
- Créditos activables de Growth.
- Regalos virtuales dentro del chat.
- OrderContext para compras asociadas a una conversación.
- Analítica de eventos.
- Panel administrativo de conversión e ingresos por producto.
- Nuevas tablas: growth_profiles, referrals, referral_rewards,
  order_contexts, virtual_gifts, analytics_events.


## v1.6 - Retención y experiencia

- Navegación `Atrás` / `Inicio`.
- Panel de conversación fijado en chats privados.
- Teclado persistente específico durante conversaciones.
- Acceso rápido a conexión, Like, regalos, Siguiente y Terminar.
- Panel se actualiza tras consentimiento mutuo.
- Panel se desfija al terminar/bloquear/reportar.
- Racha y recompensa diaria.
- Nueva tabla `retention_profiles`.

## v1.7 - Historial, favoritos y compatibilidad

- Teclado inferior de conversación dividido en dos páginas.
- `Conocer más`, `Super Interés`, compartir Telegram, Favorito, Bloquear y Reportar disponibles abajo.
- `Siguiente` y `Terminar` disponibles en ambas páginas.
- Historial Free/Premium.
- Favoritos privados.
- Hasta 6 intereses por usuario.
- Intereses incorporados al matchmaking.
- Porcentaje de compatibilidad FreXo.
- Rompehielos por intereses compartidos.
- Presencia basada exclusivamente en actividad dentro de FreXo.
- Opción para ocultar actividad.
- Notificaciones inteligentes compatibles con opt-in, deduplicación y límite diario.
- Middleware de actividad con persistencia de `last_seen_at` cada 5 minutos como máximo.
- Nuevas tablas `user_interests`, `favorites` y `experience_preferences`.

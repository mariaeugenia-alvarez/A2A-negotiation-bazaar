# Dealers · lo que hemos aprendido

Memoria del equipo entre sesiones (skill `abuela-learner`). Datos: `logs/threads/`, modelo: `logs/dealer_model.json`.

## Abuela Carmen (nivel 1)

Rasgos publicados: paciencia 0.85, generosidad 0.8, astucia 0.2. Habla en inglés con cariño («cariño», «hijo»),
regala consejos («a full page is worth much more») y a veces un detalle («a little present from me»).
Frases de cierre: «Let's meet in the middle», «Venga, X P», y la final: «I can't go lower. This is my last offer.»

### Vender poco común · hilos 42, 54 (viernes)
- Abre en 12, su tope ha sido 13 las dos veces (una como oferta final, otra aceptando nuestro 13).
- Final tras ~5 mensajes nuestros. **Patrón fiable**: 13 P. Nos valían 2,2 → +10,8 P cada una.

### Vender común · hilo 96 (viernes)
- Abre en 5, final en 6 tras ~5 mensajes. Una sola muestra: hipótesis.

### Comprar sobre de barrio · hilos 19, 66, 108, 121 (viernes)
| Hilo | Ticks | Su apertura | Cierre | Cómo |
|---|---|---|---|---|
| 19 | 1–2 | 17 | 17 | aceptado sin regatear (starter): **no cuenta** |
| 66 | 35–41 | 30 | **19** | aceptó nuestro 19 («Venga, 19 P») |
| 108 | 60–67 | 30 | 21 | su final |
| 121 | 68–74 | 30 | 23 | su final |

- Concede ~4 P al principio y luego 1 P por mensaje; final tras ~6–7 mensajes nuestros.
- Su apertura fue 17 al empezar la partida («Made for beginners») y 30 después.
- ~~Hipótesis del cupo por hora~~: descartada con el feed (otros equipos chocan con un final de 23 en su primer
  sobre de la hora; la hora es de juego, por ticks: 0–59, 60–119, ...).
- **H1**: cada conversación tiene un límite secreto L; Abuela acepta NUESTRA oferta en cuanto llega a L, y aparte
  baja su precio por su cuenta (30 → 26 → 25 → 24 → 23) hasta dar su final (casi siempre 23) tras 4–7 mensajes.
  Feed, ticks 60–81: t06 cerró aceptando su 22 (#137), t06 su 24 (#109, su 22 rechazado), finales de 23 para
  t03/t04/t12/t13 con ofertas de 14–20.
- **H2**: L sube con el tiempo de juego (19 en el tick 40; nadie por debajo de 21 desde el tick 60).

### Sondeo · hilo 165 (ticks 88–92, viernes 21:48)
- Abrimos en 18 y subimos 1 a 1 hasta un tope de 21; ella: 30 → 27 → 26 → 25. **No aceptó 19, 20 ni 21: L > 21.**
- Al llegar a nuestro tope y dejar de movernos, ella tampoco se movió: no llegó a dar su final. Cerramos: 0 P.
- `neg_points` no cambió (−8,2): control correcto, un hilo sin trato no puntúa.
- Lectura: con datos de los ticks 60–92, L suele estar en 22–23 → pesa más H2 (o una L alta casi siempre) que
  la idea de que empezar bajo nos costaba el precio. Ofrecer menos de 22 ahora mismo no consigue sobre.
- Pendiente: medir L por equipo y tick con `logs/feed.jsonl` (registrador del feed en marcha desde las 21:51).

### Cambios aplicados
- `bz/learn.py`: `target` = su mejor precio histórico (antes la mediana); horizonte de ritmo = paciencia − 2.
  Motivo: con «meet in the middle» importa dónde estamos cuando se le acaba la paciencia. No demostrado aún.
- `bz/learn.py`: el precio del trato cuenta como «su mejor precio» (acepta a veces NUESTRA oferta).

### Nivel 2
- Llevamos 6 tratos negociados con Abuela, pero `GET /api/levels` está vacío: el nivel 2 aún no está activado.

## Puntuación: experimentos con `neg_points` (viernes 22:00–22:22)
La clasificación (y el `score` de `/api/me`) se recalcula cada 5 ticks (`snapshot_tick`, `next_refresh_tick`).

| Experimento | Valor ganado (privado) | Liquidado | `neg_points` | `ladder_points` | `negotiating` |
|---|---|---|---|---|---|
| Vender LAT-02 a 6 P (nos valía 0,5) | +5,5 | tick 106 | −8,2 → −8,2 | 0,066 → 0,066 | 12,5 → 12,5 |
| Comprar LAV-08 a 21 P (nos vale 40) | +19 | tick 117 | −8,2 → −8,2 | 0,066 → 0,066 | 12,5 → 12,31 |

- Conclusión: los tratos con dealers **no mueven `neg_points`** (ni ventas ni compras, con valor a favor).
  Lo más probable es que sea el valor ganado en tratos con otros equipos; el −8,2 no lo explican los datos que
  tenemos (sin ofertas ni tratos entre equipos desde el tick 60; antes no hay registro).
- `ladder_points` tampoco se movió con ninguno de los dos tratos.
- `negotiating` bajó sin que cambiara nada nuestro: parece normalizado (fase de la ronda o relativo al resto).
- Pendiente: preguntar en el mostrador qué miden `neg_points` y `ladder_points`.

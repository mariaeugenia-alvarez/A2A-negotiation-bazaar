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

### Revisión con el feed completo (106 hilos, ticks 60–122; deep-dive del viernes 22:30)
- **Su final es un suelo oculto F por conversación** (20–25, media 22,3), independiente de nuestra trayectoria:
  corr(nº de mensajes, final) −0,16, corr(nuestro último precio, final) −0,10. «Meet in the middle» y «N concesiones»
  descartados (85 %).
- **Su primera bajada delata F**: F ≈ 30 − 2·d1, con ±1 en 16 de 17 hilos (75 %). Ej.: hilo 165, d1 = 3 → F ≈ 24 > nuestro
  límite 21; hilo 166, d1 = 5 → F = 20 (no fue por abrir en 8).
- Solo concede cuando subimos (~1 P por subida, sea cual sea el paso). Repetir precio no la mueve.
- Acepta nuestra oferta cuando llega a F (a veces F − 1) (60 %).
- **H2 descartada** (final de 20 en el tick 95). `best_ever = 19` (tick 35) está caducado: `accept_at` nunca dispara.
- Mejoras pendientes: límite 25 en vez de 23 (con 23 perdemos ~18 % de tratos), pujar F − 1 y luego F tras su primera bajada.

### Modelo de predicción · `bz/predict.py` (sábado, 165 hilos de todos los equipos, feed + nuestros)
`python3 -m bz.predict` reconstruye cada hilo, ajusta el modelo y lo compara con «1 P por movimiento».
- **Límite L por conversación; su primera bajada va a mitad de camino, redondeando hacia abajo:**
  d1 = (A − L) // 2, así que **L = A − 2·d1 o A − 2·d1 − 1**. Una sola respuesta suya da su límite con ±1 P.
  0 violaciones en 126 hilos de todos los tipos (sobre, poco común, común, y al venderle, con el signo al revés).
- Después baja ¼ de lo que le queda hasta L (mínimo 1 P), **sea cual sea nuestro paso**. Exacto en el 84-95 % de
  respuestas; si falla, por 1 P (se para 1 P antes de L).
- Acepta nuestra oferta si llega a lo que ella diría a continuación (y no pasa de L). Ofrecer menos no la convence.
- Final tras 4-7 respuestas (4 en la mitad de los casos) o al tocar L; el final cae de media 0,9 P por encima de L.
- Lo que sale de cada primera respuesta (sobre: abre 30):

| Su 1ª respuesta | Veces | Límite L | Final esperado subiendo 1 P |
|---|---|---|---|
| 25 | 12 | 19-20 | ~20,8 |
| 26 | 13 | 21-22 | ~22,4 |
| 27 | 4 | 23-24 | ~23,8 |

  Poco común (abre 29): 25 → L 20-21, 26 → 22-23, 27 → 24-25. Común (abre 12): 10 → 7-8, 11 → 9-10.
  Al venderle un poco común (puja 12): 13 → L 14-15, 14 → 16-17. Común (puja 5): siempre 5-6.
- **Jugada:** abrir lejos (la mitad de su precio), subir 1 P por mensaje sin repetir nunca, ofrecer L en cuanto ella
  solo pueda decir L, y aceptar su final. Opcional: si la 1ª respuesta es 26-27, cerrar y abrir otro hilo para volver a
  sortear L (cerrar sin trato no gasta cupo: el cupo cuenta compras). `advise()` da el siguiente precio.

## El Chato (nivel 2)
- **Activo para nosotros desde el tick 98** (desbloqueado con 4 tratos con Abuela); abre a todos en t = 2,63 h.
- Vende: comunes/poco comunes desde 33, raras desde 97 (−1 por subida nuestra, final ~91), sobre_plata 188.
- Compra poco comunes a 13 sin moverse; una rara: de 39 a 46 (final).
- Aún no hemos abierto ningún hilo con él: sus 3 mejores tratos llenan los huecos del nivel 2, que pesa más.

### Teoría, simulación y primer hilo (rama `price-limits`)
Rasgos publicados: paciencia 0.35 (Abuela 0.85), astucia 0.85, memoria 0.9, rigor 0.85. Silver pack: lista 150, apertura 188.
Simulaciones: `tests/sim_chato.py` (dealer simulado con paciencia baja; todos los supuestos están en su docstring).

**Primer hilo, 294 (ticks 148-151): vender MAL-08 (poco común), nuestro suelo 13. Sin trato:** otra sesión vendió
esa carta a Abuela en el tick 155 y el hilo cerró con `not_owner`.

| Tick | Quién | Precio |
|---|---|---|
| 148 | nosotros | 22 |
| 149 | El Chato | 13 («Veintidós, dices... trece primas») |
| 149 | nosotros | 18 |
| 150 | El Chato | 13 |
| 150 | nosotros | 14 |
| 151 | El Chato | 13 («Yo no me muevo si tú apenas te mueves. Lo tomas o te lo quedas.») |

- Su puja por un poco común empieza en 13 (50 % de la lista) y no se movió con pasos pequeños.
- Nombró su última oferta **solo con palabras**, tras 3 mensajes nuestros (sin `final: true`). El agente ya lo lee
  (`bz/texts.py: says_final`), y `learn` saca su paciencia de ese texto.
- Su puja por un poco común es la misma que la de Abuela (13): con nuestra apertura no mejora a Abuela.
- Mala coordinación: dos sesiones eligieron la misma carta. El agente ahora relee nuestras cartas antes de cada venta.

**Cruzando con los datos del feed de arriba:** vende poco comunes desde 33 (no desde 26, la lista) y casi no se mueve
(−1 por subida nuestra; una rara de 97 a 91). Dos consecuencias:
- Comprarle un poco común a nuestro límite actual (26, su lista) no cerrará: su rango real queda por encima.
- Para comprar, nuestro BATNA es Abuela (compramos LAV-08 a 21 allí). A El Chato solo le compramos si baja de lo
  que ya conseguimos con ella. Hay que reescribir los escenarios de compra del simulador con apertura 33 y paso ≈ 1.

**Segundo hilo, 505 (ticks 333-336): comprar LAV-09 (rara, nos vale 112, lista 77). Sin trato:** abrimos en 60 con
límite 93, pero el agente repartió la subida en 3 mensajes (el prior de su paciencia) y subimos de 11 en 11.

| Tick | Quién | Precio |
|---|---|---|
| 333 | nosotros | 60 |
| 334 | nosotros | 71 |
| 334 | El Chato | 97 («Sesenta no compra nada aquí. El Cine Doré, 97. Ese es mi número.») |
| 335 | El Chato | 96 |
| 335 | nosotros | 82 |
| 336 | nosotros | 93 |
| 336 | El Chato | 95 («Subiste once, yo bajo uno. 95 P. Así funciona conmigo.») |

- El hilo lo cerró el servidor (`closed`, sin motivo) justo después de nuestro 93: llegamos al límite en 3 mensajes y
  él seguía en 95.
- **Cuando vende, solo iguala pasos pequeños:** en el feed, pasos de 2-4 P reciben lo mismo; un salto grande (6, 11)
  recibe 1 P. Con él hay que subir de ~4 en ~4 durante unos 8 mensajes (`--patience 8`). Los hilos de raras del feed
  duraron 8-9 mensajes sin palabra final.
- `tests/sim_chato.py` ya está recalibrado con el feed y con este hilo: reproduce el 0/48 de este ritmo, y con apertura
  60 y ritmo de 8 cierra 48/48 a ~85,5 de media.

**Tercer hilo, 526 (unos minutos después): comprar LAV-10 (rara, nos vale 112). Trato a 84:**
`agent.py buy-card LAV-10 --dealer chato --open 60 --limit 93 --patience 8 --force` (`--force`: el hilo 505 dejó
«su mejor precio 95», por encima del límite, y sin él el agente ni abre).

| Nosotros | 60 | 64 | 68 | 72 | 76 | 80 | 84 ✔ |
|---|---|---|---|---|---|---|---|
| El Chato | 97 | — | 95 | 93 | 89 | 85 | acepta |

- Con pasos de 4 bajó 2, 2, 4, 4 y aceptó nuestro 84 en el 7º mensaje: igualó el paso, como predijo el simulador.
- 84 es el segundo precio más bajo del feed (solo t04 sacó 82), y nos deja ~28 de ganancia sobre el valor.
- La memoria de 0,9 no se notó: el hilo 505 fallido no le hizo endurecerse.

**Cuarto hilo, 543 (minutos después): comprar LAV-09 (nos valía 218: completaba la página LAV). Trato a 89 (su final):**
misma orden con LAV-09. Ahora `learn` sacó objetivo 84 del hilo 526, y el agente subió de 3 en 3.

| Nosotros | 60 | 63 | 66 | 69 | 72 |
|---|---|---|---|---|---|
| El Chato | 97 | 96 | 95 | 92 | 89 FINAL → aceptamos |

- Esta vez dio su final pronto (5º mensaje) y más alto. Dos posibles causas que aún no sabemos separar: pasos de 3
  en vez de 4, o su memoria (segunda compra seguida en pocos minutos). Siguiente prueba: pasos de 4 y dejar más
  tiempo entre compras.
- Página LAV completa. Puntuación 12,18 → 16,58 y puesto 16º → 12º tras los dos tratos (otra sesión con nuestra clave
  también estaba operando).

**Modelo de predicción (`bz/predict.py`, 72 hilos del feed y nuestros): Boulware con reciprocidad.**
- Lo más que ha cedido en total en su respuesta k es floor(a·k² + b): nada al principio, cada vez más rápido.
  a ≈ 0,48 en raras, 0,10 en poco comunes, 0,06 cuando nos compra un poco común (b = 0,5 / 0).
- En cada respuesta cede **lo menor entre nuestro paso y lo que le deja su calendario**. Eso explica sus frases:
  «Subiste once, yo bajo uno» (su calendario solo daba 1 en esa respuesta) y «no me muevo si tú apenas te mueves».
  Un salto grande más tarde sí lo iguala (hilo 195: paso de 6 en la 5ª respuesta → bajó 6). Así que el salto grande no
  se castiga: es demasiado pronto.
- Predice cada concesión, dejando fuera el hilo a predecir: exacto en el 77 % (raras), 96 % (poco comunes al comprar)
  y 87 % (poco comunes al venderle), contra 49 %, 44 % y 15 % de «igualar hasta 1 P».
- Hilo 526 (pasos de 4, trato a 84): el modelo reproduce todo el hilo, incluida la aceptación de nuestro 84.
- **Jugada:** pasos que sigan su calendario (rara: 1, 2, 2, 4, 4, 5...) y, cuando el siguiente paso nos junte, ofrecer
  el punto medio (él iguala el paso). Con el simulador del modelo: igual que pasos de 4 si su paciencia es 4-5
  (89, 85), mejor si dura 6+ (80-78 frente a 84). **Ojo:** 78-80 está por debajo de todo lo visto (mínimo 82); su
  límite real puede cortar antes.
- Poco comunes: le cuestan ~29 tras 6 respuestas, peor que Abuela (21-25): no comprárselas a él.

**Doña Pilar:** sin datos para un modelo: 8 hilos, todos de t13 vendiendo poco comunes a 49-51 alternando precios
(eso no es moverse). Puja 16 y no se movió nunca.

**Prior para dealers nuevos (agrupado, aparte de los datos de cada dealer):** mensajes antes de su final ≈ 6 × rasgo de
paciencia (Abuela 0,85 → 5-7; El Chato 0,35 → 3 observado, 2 con el prior). `learn.messages_per_trait` lo calcula con
los dealers que ya conocemos, y un hilo real sustituye al prior.

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

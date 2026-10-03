# The Bazaar · Hoja de negociación (maestra, v5)

Sábado 3 oct 2026, 13:05 (tick 583) · Equipo 9 · Versión en inglés: `ONE_SHEET.md` · Ciclos y experimentos: `PLAYBOOK.es.md`
**Esta hoja es la fuente de verdad para hoy y mañana.** Estrategia aprobada por Thameur a las 13:35, salvo el día de entrega, que sigue siendo una hipótesis. Si otro documento dice otra cosa, manda esta. Corrige el
otro documento.
Fuentes: `RULES.md`, diapositivas del kickoff, Pistas del Día 2, **diapositivas de Duelos de la organización**,
`GET /api/schedule`, nuestros registros (`logs/score.jsonl`, `logs/duels/`, `TRADES.md`, `DEALERS.md`).
✅ = comprobado en una fuente o en nuestros datos · ⚠️ = inferencia mía · ❓ = no sabemos
Forma tomada de *Never Split the Difference* (Voss), apéndice «Negotiation One Sheet»: meta, resumen, etiquetas,
preguntas calibradas, ofertas no monetarias. Nos quedamos con lo que funciona en un juego donde el código pone los
precios y cada ronda de charla cuesta puntos. La sección VIII dice qué tomamos y qué dejamos fuera.

---

## 0. Dónde estamos (tick 583) ✅

| | Mañana (tick 249) | Ahora (tick 572) | Comentario |
|---|---|---|---|
| **Puntuación total** | 10,4 · puesto 16 | **20,2 · puesto 15** | Máximo 23,0 y puesto 9 en el tick 470; luego los demás equipos nos alcanzaron |
| Negociación (de 30) | 4,8 | 12,7 | **Relativa al resto**: el equipo mediano pasó de 10,8 a 16,2 |
| Mercado (de 30) | 4,8 | 7,5 | Puesto gratis. Eficiencia del Market Test 0,899 → 0,933. Los mejores: 10,6–12,1 |
| `neg_points` (tratos con equipos) | 0 | **23,5** | Nuestra mayor fuente. ≈ el valor ganado en tratos con equipos (+24 según `TRADES.md`) ⚠️ |
| `duel_points` | 0 | **5,98** | Duelos I: 18 tratos de 30 |
| `ladder_points` (dealers) | 0 | **0,14** | 13 tratos con dealers casi no lo movieron |
| Dinero · cartas | 501 P | 326 P · 33 cartas | **Página de Lavapiés completa** (+106 P de valor en cada una de sus cartas) |

**Qué significa:** nuestros puntos vinieron de los tratos con equipos y de los duelos. Los dealers casi no han dado
puntos. Como la puntuación es relativa, quedarse quieto hace perder puestos.

---

## I. LA META

**Meta del sábado (el mejor caso, por escrito para no conformarnos con menos): entre los 8 primeros a las 23:00.**
**Meta del domingo: entre los 5 primeros al congelar la puntuación.**

| Carril | Objetivo concreto | Por qué es alcanzable |
|---|---|---|
| **Duelos II (≈18:30)** | **Ningún duelo sin respuesta.** Tratos ≥ 80 %. Mediana ≤ 2 rondas. Resultado medio por trato ≥ 18 | Duelos I: los tratos en ≤ 2 rondas dieron de media **20,4**; los de ≥ 4 rondas, **5,7**. Nuestro silencio nos costó 8 duelos |
| **Tratos con equipos** | `neg_points` de 23,5 a **45** a las 23:00. Cada trato debe ganar valor | Seis tratos pequeños ya dieron +24. El quoter está listo (no en vivo) |
| **Páginas** | Completar **Salamanca** (faltan SAL-06, 07, 09, 10). No romper nunca Lavapiés | Bono de página = +25 % del total de la página en cada carta ✅ |
| **Dealers** | Solo tratos que ganen valor: cartas de página compradas por debajo de su valor, repetidas vendidas por encima. **Nunca una venta por debajo de nuestro valor, nunca una carta de página** | Los dealers dan muy pocos puntos. Sirven para cartas baratas y desbloqueos, no para puntos |
| **Mercado** | Mantener 7,5 o más. Decidir sobre el broker de Maru antes del Market Test duro (≈21:30) | Los mejores equipos están en 10,6–12,1 |

Los cuatro pasos de Voss para la meta: fijarla, escribirla, decírsela a una compañera (Maru), llevarla encima.
**El peor caso que no aceptamos:** un trato fuera de nuestro límite, una venta por debajo de nuestro valor, un duelo sin
respuesta.

### Reglas fijas (nunca se rompen, ni en código ni a mano)
1. **Duelos: nunca cruzar nuestro límite.** Como vendedor, nunca por debajo de nuestro coste; como comprador, nunca por encima de nuestro valor. Cruzarlo resta puntos y no le da nada al rival ✅ (diapositivas de la organización).
2. **Nunca vender una carta por debajo de lo que vale para nosotros. Nunca vender una carta de una página completa ni una que nos falte para una página.**
3. **Nada EN VIVO sin el visto bueno de Thameur.** Analizar es gratis; negociar gasta primas reales.
4. **Un dueño por carril en nuestra clave compartida:** dealers = scripts de Maru, tratos con equipos = `trader.py`, duelos = `duels.py`. Antes de publicar una oferta, avisar en la otra terminal.
5. **Los precios los pone el código.** Las palabras llevan el precio y piden información. Nunca deciden el precio.

### Qué ha cambiado desde la v4 (esta mañana)
- **Medido:** tratos con equipos → `neg_points`, tratos con dealers → `ladder_points`, duelos → `duel_points` ✅. Los 30 puntos de negociación mezclan los tres y son **relativos a los demás equipos** ✅ (los nuestros subieron a 15,5 y bajaron a 12,7 mientras la mediana subía).
- **Medido:** puntuación del duelo = **nuestro excedente × (1 − decaimiento)^rondas**, exacto. Duelo 2549: excedente 33 × 0,94 = 31,0. Duelo 2327: 40 × 0,94² = 35,3 ✅.
- **Nuevo de la organización:** te enfrentas a **cada equipo dos veces** (una como vendedor, otra como comprador). Un mensaje por tick. Un acuerdo se liquida en el tick siguiente. Los duelos tienen sus propios límites y nunca bloquean el comercio ✅.
- **Nuevo en el calendario:** Duelos II con **8 % de decaimiento, 16 ticks y hasta 6 duelos a la vez**. Duelos III y la Final con **10 % y solo 12 ticks** (3 minutos con los ticks de 15 s del domingo) ✅.
- **Nuevo:** Doña Pilar comercia. Fiebre de Salamanca **≈16:00–18:00**: paga un 25 % sobre catálogo por Salamanca ✅ (calendario).
- **Nuevo:** Radio Rastro (`GET /api/news`). Algunas noticias son ciertas y mueven el mercado; otras son rumores ✅. Tratar las noticias como pista, nunca como hecho.
- **Aviso:** en el tick 567 `neg_points` bajó por primera vez (24,2 → 23,5), justo después de que los scripts de dealers vendieran a Pilar MAL-08 (21 P, vale 22,5) y SAL-07 (24 P, vale 27,5, carta de la página de Salamanca). Causa sin probar ⚠️. La regla fija 2 ya lo cubre.

### Valor de las cartas (sin cambios, comprobado) ✅
- Valor = catálogo × nuestro multiplicador del barrio × factor de copia, más el bono de página si la página está completa. **El trader lee los valores del juego** (`your_value` incluye el bono).
- Catálogo: común 10, poco común 25, rara 70, épica 180, legendaria 450. Factor de copia: 1.ª 1,0; 2.ª 0,25; 3.ª y siguientes 0,1.
- Nuestros multiplicadores: Lavapiés 1,6 (**completa**), El Retiro 1,3, Salamanca 1,1, Malasaña 0,9, Chamberí 0,7 (sale el domingo), La Latina 0,5.
- **Paga la comisión quien acepta** ✅. El Rastro: 5 % + 1 P por carta. Si aceptan nuestra oferta, cobramos el precio entero.
- Un trato con un dealer al precio con el que abre no cuenta ✅. Solo cuentan los 3 mejores tratos por dealer ✅.
- Bono de maestro (10 % en el catálogo): ❓ sin medir. No tenemos página maestra.

---

## II. RESUMEN (lo que cada parte debería contestar con un «Así es»)

Sirve como primera frase de un mensaje o como marco detrás del código. Cuenta los hechos desde **su** lado.

| Contraparte | Resumen |
|---|---|
| **Rival de duelo** (un agente LLM de otro equipo ✅) | «Cada ronda que hablamos, la tarta se encoge para los dos (6–10 %). Si nadie contesta, los dos sacamos cero. Quieres un trato rápido y justo dentro de tu límite, y nosotros también.» |
| **Rival de duelo, precio + día** | «A cada uno nos importa distinto el día de entrega. Si el día se lo queda quien más lo valora, la tarta crece para los dos, y al otro se le paga con precio.» |
| **Otros equipos** | «Estás completando páginas, y una carta que te falta vale para ti mucho más que una repetida para nosotros. Tus ofertas caducan en unos 2 ticks, así que quieres respuestas rápidas y claras.» |
| **Abuela** | «Eres paciente, solo te mueves cuando nos movemos, y premias a los clientes amables y constantes. Una página completa vale más que cartas sueltas.» |
| **El Chato** | «Tratas derecho. No te mueves por pasos diminutos y nunca das más de lo que damos.» |
| **Doña Pilar** | «Coleccionas lo que otros tiran. Pagas por encima del catálogo por las cartas que te gustan, y esta tarde tienes fiebre de Salamanca.» |

## III. ETIQUETAS / AUDITORÍA DE ACUSACIONES

**Dónde las palabras pueden contar:** rivales de duelo y otros equipos, que son agentes LLM con deseos ocultos ⚠️.
**Con los dealers, las palabras nunca mueven el precio** ✅ (lo decide su código). Ahí las etiquetas solo compran
información y buena relación.
**Regla de coste:** una etiqueta va en el **mismo mensaje que un precio**. Nunca cuesta una ronda extra.

| Quién | Acusación que puede hacer | Etiquetas (una por mensaje) |
|---|---|---|
| **Rival de duelo** | «Abres muy codicioso / pierdes rondas» | Parece que quieres cerrar esto rápido. · Parece que te importa un reparto justo. · Parece que el día de entrega te importa mucho. |
| **Otros equipos** | «Ignoráis ofertas / ofrecéis poco / se la vendisteis a otro» | Parece que esta carta completa tu página. · Parece que te importa la rapidez, porque las ofertas caducan pronto. · Parece que te han ignorado ofertas antes. |
| **Abuela** | «Regateas duro» (sus palabras) | Parece que has conocido a muchos regateadores duros. · Parece que valoras a los clientes amables. |
| **El Chato** | «Te estás haciendo el listo» | Parece que valoras el trato derecho. · Parece que los pasos pequeños no te impresionan. |
| **Pilar** | «Solo venís cuando pago más» | Parece que Salamanca te llega al corazón. · Parece que sabes ver lo que otros pasan por alto. |

Auditoría de acusaciones para los duelos, una vez, con nuestro precio de apertura: *«Seguramente pensarás que esta
apertura es algo firme. Está pensada para cerrar en una o dos rondas sin perder tarta.»*

## IV. PREGUNTAS CALIBRADAS (Qué / Cómo, nunca Por qué)

| Quién | Preguntas | Qué hacemos con la respuesta |
|---|---|---|
| **Rival de duelo, precio + día** | ¿Cuánto te importa el día de entrega? · ¿Qué te cambiaría un día antes (o después)? | El día para quien más lo valora. Su respuesta es una pista; sus **cambios de día por precio** son la prueba |
| **Rival de duelo, solo precio** | ¿Qué haría que esto te funcione ahora mismo? | Nada en el código. Las palabras no cambian nuestro límite |
| **Otros equipos** | ¿Cómo encaja esta carta en tu página? · ¿Qué haría que este cambio te funcione? · ¿Qué más te falta? | Sus huecos nos dicen cuánto valen para ellos nuestras repetidas. Los llenamos con ofertas fijas de venta |
| **Abuela** | ¿Qué buscas en un cliente? | Solo buena relación. Su precio sigue su regla (`bz/predict.py`) |
| **El Chato** | **No preguntar.** Cada mensaje a él lleva un precio nuevo, o cuenta como spam | |
| **Pilar** | ¿Qué cartas buscas hoy? | Nos dice qué repetidas llevarle |

## V. OFERTAS NO MONETARIAS

| Quién | Qué puede dar además de dinero |
|---|---|
| **Rival de duelo** | **El día de entrega (0–10)** ✅. Cambiar el día que menos nos importa por precio |
| **Otros equipos** | Cambios carta por carta ✅ (nuestras dos LAV-06 repetidas por cartas de su página). **Ahorro de comisión:** si aceptan nuestra oferta fija, pagan ellos ✅. Ofertas fijas de larga duración (`expires_in_ticks` hasta 120) |
| **Abuela** | Regalos (nos regaló una carta en el hilo 108) y consejos («una página completa vale mucho más», «cambia tus repetidas») ✅ |
| **El Chato** | Mejores sobres y raras sueltas ✅. **Tres buenos tratos desbloquean antes al siguiente dealer** ✅. Le compramos LAV-09/LAV-10 por debajo de su valor (+23, +28) |
| **Pilar** | Paga **por encima del catálogo** por las cartas que le gustan ✅. Vende sobres de oro ✅ |

---

## VI. DOCTRINA DE DUELOS (Duelos II, III y la Final)

### Lo que nos enseñaron los Duelos I ✅ (30 duelos, sesión 2, de `logs/duels/`)
| Hecho | Cifra |
|---|---|
| Tratos | 18 de 30 (60 %). En práctica: 53 % |
| **Tratos en ≤ 2 rondas** | 8 tratos, resultado medio **20,4** |
| **Tratos en ≥ 4 rondas** | 8 tratos, resultado medio **5,7**. El peor: duelo 2486, 9 rondas, resultado 0,6 |
| **Nuestro agente calló del tick 503 al 553** | **8 duelos perdidos:** 5 en los que el rival ofreció dentro de nuestro límite (2485: subió hasta 106 sobre nuestro coste de 85, y no le contestamos) y 3 que ni abrimos. Unos +60 de resultado perdidos (≈ +25 % sobre nuestro total) |
| Los rivales abren a menudo **dentro de nuestro límite** | 2338, 2549, 2325: aceptar rápido dio 12–31 |
| Los rivales corresponden | Un paso real nuestro trae un paso real suyo. Pasos de 1 P traen pasos de 1 P y queman rondas |

### Las reglas para Duelos II, III y la Final (aprobadas por Thameur, 13:35)
1. **Contestar cada duelo desde su primer tick.** Ningún silencio por accidente. Ejecutar `python3 duels_watch.py` (hecho, b5b9c13): arranca `duels.py` cuando hay duelos en vivo, lo reinicia si se cae o si un duelo lleva 3 ticks esperándonos, y avisa con DUEL_START / DUEL_SILENT / DUEL_CRASH en `logs/alerts.jsonl`. **Solo UNA máquina lo ejecuta** (la de Thameur o la de Maru), o dos agentes hablarían en los mismos duelos ❓ quién ejecutó los Duelos I.
2. **Nuestro límite es firme.** Como vendedor, nunca por debajo de nuestro coste; como comprador, nunca por encima de nuestro valor. Todo lo demás se adapta.
3. **Primera oferta: ambiciosa, pero que el rival pueda aceptar.** Nada de anclas extremas. Dónde cerraron los tratos de Duelos I ✅: como comprador, entre 0,69 y 0,99 de nuestro límite (mediana ≈ 0,87); como vendedor, entre 1,04 y 1,46 (mediana ≈ 1,22). Nuestro código abría a 0,55 / 1,45, fuera de esa zona. **Punto de partida propuesto, a comprobar en simulación:** comprador ≈ 0,75 × límite, vendedor ≈ 1,30 × límite ⚠️.
4. **Leer al bot que tenemos delante y adaptarnos en tiempo real** (bloque siguiente). De ahí sale el precio extra.
5. **Regla de aceptar:** aceptar su oferta si está dentro de nuestro límite y lo que aún podemos ganar es **menos de lo que cuesta una ronda más** (8 % o 10 % del excedente en la mesa), o si quedan menos de 3 ticks.
6. **Como mucho 2 contraofertas**, cada una un **paso real** (nada de pasos de 1 P). Después, aceptar la mejor oferta dentro de nuestro límite.
7. **Si sus ofertas nunca entran en nuestro límite, no cerrar es lo correcto** (duelo 2487).
8. **Cada mensaje con precio en Duelos II/III incluye `days`** (si no, `400 missing_days`) ✅.

### Leer al bot: lo que muestran los Duelos I y la práctica ✅ (61 duelos, `logs/duels/`)
- **Una ronda es un intercambio, no un tick.** Solo cuenta cuando él contesta a una oferta nuestra. Si solo habla él, el contador de rondas sigue en 0 (duelo 286: 12 mensajes suyos, 0 rondas; duelo 2485: subió de 53 a 106, 0 rondas).
- **Los bots ceden aunque nos callemos:** en 89 de 104 casos su siguiente oferta se movió a nuestro favor sin mensaje nuestro, **4,2 P** de media. Tras un mensaje nuestro se movió **6,0 P** de media.
- **Más o menos la mitad de los bots abre ya dentro de nuestro límite** (12 de 25 cuando compramos, 9 de 25 cuando vendemos).
- **Los alias no son equipos.** Los mismos 8 nombres (Rival Oro, Plata, Rojo…) salen en muchos duelos. No podemos recordar a un equipo por su alias.

**Cómo nos adaptamos a cada bot (lo decidimos con sus 1–3 primeros mensajes):**
| Qué hace el bot | Qué hacemos |
|---|---|
| **Abre dentro de nuestro límite con buen excedente** | Como mucho una contraoferta real para probarle, luego aceptar. No quemar una ronda por poco |
| **Sigue cediendo solo mientras nos callamos** (va por tiempo) | **Callar y dejar que venga.** No cuesta ninguna ronda. Aceptar la mejor oferta dentro de nuestro límite cuando dejen de llegar pasos o 2–3 ticks antes del plazo |
| **Solo se mueve cuando nos movemos** (recíproco) | Pasos reales nuestros: responde en proporción (práctica: nuestros pasos de 1–5 P trajeron 5–14 P de Rival Rojo). Hasta 2 contraofertas, luego aceptar |
| **Casi no se mueve o sigue fuera de nuestro límite** (duro) | Un paso real para probarle. Si sigue sin entrar en nuestro límite, no cerrar es lo correcto |
| **Responde a nuestras palabras** (repite, etiqueta, pregunta) | Anotarlo. Las palabras van con el precio y nunca cambian nuestro límite |

### El día de entrega (Duelos II y III): una hipótesis, todavía no una regla ⚠️
- ✅ Cada parte tiene un `your_days_weight` privado (una ganancia o un coste por día). El trato vale para cada parte excedente de precio + peso × día. La organización: «da el día a quien más lo valore y cámbialo por precio».
- **Dirección de Thameur:** usar el día como **palanca combinada con nuestro precio**, no como un empujón automático al día 0 o 10.
- **Hipótesis a probar en Duelos II:** leer qué día pide primero y cuánto precio da cuando el día se mueve. Luego ofrecer paquetes en los que cedemos en el día que le importa y lo recuperamos en precio. Comparar el resultado por trato con y sin movimientos de día.
- **Antes de las 18:30:** `duels.py --dry` en un duelo de dos temas, y comprobar que `days_meaning` se lee con el signo correcto.

### Calendario de duelos ✅ (de `/api/schedule`, hora de Madrid estimada desde el tick 583 a las 13:03)
| Sesión | Hora real ≈ | Reloj | Decaimiento por ronda | A la vez | Temas |
|---|---|---|---|---|---|
| Duelos II | **Sáb 18:30** | 16 ticks (8 min) | 8 % | hasta 6 | precio + día |
| Duelos III | **Dom 11:30** | 12 ticks (3 min) | 10 % | hasta 4 | precio + día |
| Gran Final | **Dom 14:30** | 12 ticks (3 min) | 10 % | hasta 4 | precio + día, en la pantalla grande |

---

## VII. LOS OTROS CARRILES

### Tratos con equipos (`trader.py`, dueña: sesión del trader) ✅
- **Comprar:** valor recibido − dinero − comisión > margen. **Vender:** nunca por debajo de nuestro valor, primero las repetidas, nunca una carta que nos falte para una página.
- **Quoter (hecho, no en vivo):** pujas fijas por las cartas que nos faltan y ofertas de venta de repetidas. El guardián lo para cuando debe. Plan del tick 568: pujas RET-02..05 a 8, SAL-06/07 y MAL-06/08 a 20, RET-09 a 68, venta de la LAV-06 repetida a 20. 180 P comprometidas, +79 de valor si todo se llena. **Necesita el visto bueno de Thameur.**
- **Lecciones de esta mañana:** nunca ofrecer una carta a dos equipos a la vez. Abrir las ventas por encima de la mejor puja vista. Revisar las pujas viejas (si se llenan después de conseguir la carta por otro lado, compramos una repetida que vale el 25 %).

### Dealers (scripts de Maru: `agent.py`, `bz/predict.py`, `DEALERS.md`) ✅
- **Abuela:** su primera respuesta delata su límite (L = A − 2·d1). Error del modelo ≈ 0,4–0,7 P.
- **El Chato:** calendario a·k², nunca cede más que nuestro paso. Modelo exacto en 77–98 %. Raras de 97 a 79 en 6 respuestas.
- **Pilar:** compra MAL/SAL cerca del catálogo. **Fiebre de Salamanca ≈16:00–18:00 (+25 % sobre catálogo).** Decisión del equipo: venderle Salamanca solo si renunciamos a completar Salamanca.
- **Arreglo pendiente (Maru):** los scripts deben rechazar cualquier venta por debajo de nuestro valor y cualquier carta que nos falte para una página.

### Mercado ✅
- Puesto gratis: eficiencia 0,933, mercado 7,5. Los mejores equipos: 10,6–12,1.
- ✅ **En el tick 575 alguien abrió con nuestra clave un puesto propio, v21** (tablón, 0 % de comisión, 270 P con una fianza de 250 P que se recupera más tarde). El puesto gratis v12 se cerró. La caja bajó a 75 P. En la máquina de Thameur no corre ningún broker para v21. Un tablón sin broker sacó 3,33 en el Market Test 1 (Equipo 13). ❓ ¿Quién lo abrió, y corre el broker de Maru (`broker.py`, c9d2ea1) antes del Market Test 3 (≈13:50)?
- Market Tests a las ≈13:50, 15:50, 17:50, 19:50, **21:30 (duro: traders más firmes e impacientes)**, 21:50. El domingo, cada 2 h desde ≈10:00.

---

## VIII. QUÉ TOMAMOS DEL LIBRO Y QUÉ DEJAMOS FUERA

| De *Never Split the Difference* | Veredicto | Por qué |
|---|---|---|
| Una meta concreta y ambiciosa, escrita y compartida | **Tomado** (sección I) | No cuesta nada. Evita conformarse con el primer número |
| Un resumen que consiga un «Así es» | **Tomado** para duelos y equipos | Los rivales son agentes LLM. Un marco común puede acelerar el trato ⚠️ |
| Etiquetas y auditoría de acusaciones | **Tomado, una por mensaje con precio** | Gratis si va con un precio. **Nunca con dealers para el precio**: decide su código |
| Preguntas calibradas Qué/Cómo | **Tomado** para el día de entrega y los tratos con equipos | Buscan información oculta (el peso del día del rival, los huecos de página del equipo). Ahí las palabras pueden pagar |
| Ofertas no monetarias | **Tomado** | El día de entrega y los cambios de cartas son moneda no monetaria real aquí |
| Regateo Ackerman (65 → 85 → 95 → 100 %) | **Fuera** | Cuatro rondas cuestan un 22–34 % de la tarta al 6–10 % por ronda. Los Duelos I lo demostraron: tratos en ≥ 4 rondas dieron 5,7 de media frente a 20,4 |
| Anclas extremas | **Fuera** | La regla de la organización es «abre con una oferta que la otra parte pueda aceptar». Cada ronda de distancia cuesta puntos |
| Números precisos, no redondos (37, no 40) | **Tomado** | Gratis. Indica un precio calculado |
| «Mejor sin trato que con un mal trato» | **Tomado** como regla fija | Un trato fuera del límite resta puntos |
| Construir relación largo rato, voz de DJ de madrugada, espejos para ganar tiempo | **Fuera** | Un mensaje por tick, y el tiempo cuesta tarta. Texto y código, sin voz |
| Cisnes negros (hechos ocultos que lo cambian todo) | **Tomado como hábito** | Leer el calendario, `/api/news` y el feed: la fiebre de Pilar y el decaimiento de los duelos eran cisnes negros a la vista de todos |

---

## IX. CALENDARIO Y DECISIONES

### Hoy (Madrid, estimado desde el calendario)
| ≈ Cuándo | Qué | Quién |
|---|---|---|
| 13:50 | Market Test 3 | solo lectura |
| 15:50 | Market Test 4 | solo lectura |
| **16:00–18:00** | **Fiebre de Salamanca de Pilar** | scripts de dealers (Maru), solo si el equipo está de acuerdo |
| 17:50 | Market Test 5 | |
| **18:00** | **Ensayo en seco de `duels.py` en un duelo de dos temas. Decidir qué máquina ejecuta `duels_watch.py`** | sesión del trader + Thameur |
| **18:30** | **Duelos II** (8 %, 16 ticks, hasta 6 a la vez) | `duels.py` |
| 19:50 · 21:30 (duro) · 21:50 | Market Tests | |
| 23:00 | Cierran las puertas | |

### Domingo
≈09:00 abre (ticks de 15 s) · ≈09:30 empieza la ronda 3 desde cero, **sale Chamberí**, +150 P para todos ·
**≈11:30 Duelos III** · ≈14:30 cierran los dealers y **Gran Final** de duelos · 15:00 cierran las puertas · ≈15:30 se congela la puntuación.

### Decisiones para Thameur y Maru ahora
1. **¿Quoter EN VIVO?** 180 P en pujas fijas por cartas de página, +79 de valor si todo se llena.
2. **Maru:** bloquear las ventas a dealers por debajo de nuestro valor y las de cartas de página. ¿Vendemos Salamanca a Pilar durante la fiebre o completamos la página?
3. **Duelos II:** ✅ doctrina de la sección VI aprobada a las 13:35 (el día de entrega sigue siendo una hipótesis). La sesión del trader la pasa a `bz/duel.py` y la prueba en simulación antes de las 18:00. **Y: ¿qué máquina ejecutó `duels.py` en los Duelos I? Solo una puede ejecutar `duels_watch.py`.**
4. **Mercado:** v21 está abierto. ¿Quién le pone un broker y desde cuándo? Si no, puede sacar menos que el 7,5 del puesto gratis.
5. **Quién vigila la puntuación** durante los Duelos II (`observe.py tag D2`).

### Preguntas abiertas ❓
- La fórmula exacta que convierte `neg_points`, `duel_points` y `ladder_points` en los 30 puntos de negociación.
- Por qué bajó `neg_points` en el tick 567.
- El bono de maestro.
- Si las palabras cambian el precio de un rival LLM (probar una redacción contra otra, primero en tratos con equipos).

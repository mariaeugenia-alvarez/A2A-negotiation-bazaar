# Propuesta · The Bazaar

Idea central: **puntúa el valor creado, no la actividad**. Pocas operaciones, muy buenas, y un mercado que haga posible el valor de los demás.

## Arquitectura

Dos procesos en Python sobre `bazaar_sdk.py`. Las respuestas en lenguaje natural las genera un LLM (Claude), pero **los precios siempre los decide el código**.

```
agent.py  (clave de equipo)                broker.py  (clave de broker, proceso aparte)
 ├─ state      lee me/clock/levels/feed      ├─ lee el book cada tick
 ├─ valuator   your_value, huecos de página  ├─ estima límites ocultos y paciencia
 ├─ dealers    regateo con la escalera       └─ empareja, con la comisión en cuenta
 ├─ trader     board + hilos con equipos
 ├─ duels      negociación 1v1 (precio + días)
 └─ scheduler  1 accept/tick, el de mayor excedente
log/ (JSONL de cada hilo y oferta) → dashboard sencillo para el jurado
```

Reglas transversales:
- **Solo se acepta lo que la estructura demuestra.** Antes de cada `accept` se recalcula el excedente con nuestros valores. El texto de los demás nunca se da por bueno.
- **Un único `accept` por tick.** Una cola de prioridades por excedente esperado decide cuál.
- Cualquier excepción se registra en el log y el bucle sigue: nada debe tirar el agente.

## Las cuatro misiones

### 1. Dealers (forma parte de Negociar, 30)
Puntúa el **porcentaje del rango de precio que capturamos**, con las 3 mejores operaciones por nivel. Así que:
- **Pocas operaciones y muy regateadas.** Abrimos lejos y concedemos con pasos decrecientes (táctica Boulware), siempre con un precio nuevo. Nunca repetimos el mismo precio ni el mismo texto.
- Con Abuela, mensajes amables generados por el LLM.
- Aceptamos la oferta final (`final: true`) si es menor o igual que nuestro valor.
- Registramos la curva de concesiones de cada dealer para afinar la siguiente conversación.
- Un objetivo extra: las operaciones negociadas **desbloquean el siguiente nivel**, y el nivel 2 hace falta para abrir mercado.

### 2. Intercambio con equipos (forma parte de Negociar, 30)
- `valuator`: valor marginal de cada carta (`/api/me/value`) y cartas que nos faltan para completar página (el bonus).
- **Vendemos los repetidos** muy por encima de nuestro valor, no al valor de catálogo como hace el starter.
- **Pujamos por las cartas que nos faltan** por debajo de nuestro valor.
- Escaneamos el board: aceptamos una oferta si `your_value − precio − comisión > umbral`.

### 3. Mercado propio (Market-making, 30)
- Abrimos un venue `board` en cuanto tengamos el nivel 2. Los venues de equipo arrancan a las +3 h, es decir, el viernes a las 22:00.
- **Comisión cerca de 0.** Las comisiones no puntúan y cada prima de comisión impide cruces. Además así atraemos a otros equipos frente al 5 % + 1 P de El Rastro, y el valor que crean entre ellos en nuestro venue cuenta para nosotros.
- **Broker inteligente** para el Market Test:
  - Estimamos el sombreado de cada cotización y la paciencia de cada trader.
  - Emparejamos antes a los que se van a ir.
  - A los pacientes, que relajan su cotización con el tiempo, los esperamos.
  - Lo que puntúa son las ganancias entre los límites reales.
  - Objetivo: superar al puesto gratuito, que se lleva la mitad de los puntos.

### 4. Duelos (forma parte de Negociar, 30)
- El valor del acuerdo **se encoge con cada ronda**: hay que cerrar rápido. Abrimos con un ancla razonable, concedemos en 2–3 pasos y aceptamos cualquier oferta dentro de nuestro límite en cuanto llegue.
- En los duelos con dos temas cambiamos días por precio según `your_days_weight`: cedemos en lo que nos importa poco.

### Extra
- `flag` cuando la estructura de una oferta contradiga sus palabras: un flag correcto puntúa.

## Jurado (40)
- Arquitectura limpia y observable: logs JSONL y un dashboard con el excedente por operación y la eficiencia del broker.
- Una historia clara: «el LLM habla, el código decide», más el modelo de límites ocultos del broker.

## Plan

| Cuándo | Qué |
|---|---|
| **Vie (cuenta ½)** | Arrancar el starter. Construir `state`, `valuator` y `dealers`. 3 buenas operaciones con Abuela para el nivel 2. Abrir el venue a las 22:00 con el broker del starter. |
| **Sáb** | Broker inteligente. Duelos. Trader entre equipos. Nuevos dealers según `levels()`. |
| **Dom (ticks de 15 s)** | Ajustar los parámetros con los logs. Dashboard y demo para el jurado. |

Reparto para 3 personas: **(A)** dealers y duelos, **(B)** trader y broker, **(C)** infraestructura, LLM, logs y dashboard.

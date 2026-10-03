"""Words for dealers. Abuela likes kindness; every other dealer gets a short, plain, truthful tone.
Every message carries a new price, and no text repeats in a thread."""
import random

BUY = [
    "¡Buenas tardes, Carmen! Qué puesto tan bonito. ¿Le parecerían bien {p} primas?",
    "Gracias por su paciencia, Carmen. ¿Podríamos dejarlo en {p}?",
    "Me encanta venir a su puesto. Subo un poquito: {p} primas, ¿qué me dice?",
    "Usted sí que sabe de cromos. ¿Y si quedamos en {p}?",
    "Se lo agradezco mucho, de verdad. Le ofrezco {p}, con todo mi cariño.",
    "Mi abuela también tenía un puesto así. ¿{p} primas le vendría bien?",
    "Un pasito más por mi parte: {p}. ¡Muchas gracias, Carmen!",
    "Qué gusto hablar con usted. ¿Lo dejamos en {p}?",
    "Hago un esfuerzo, Carmen: {p} primas. ¿Trato hecho?",
    "Es usted un sol. ¿{p} y me lo llevo encantado?",
]
SELL = [
    "¡Hola, Carmen! Le traigo un cromo repetido, en perfecto estado. ¿{p} primas?",
    "Está como nuevo, se lo prometo. ¿Le parecen bien {p}?",
    "Gracias por mirarlo con calma. Bajo un poquito: {p}.",
    "Para usted, que es la mejor del Rastro: {p} primas.",
    "Me hace mucha ilusión que lo tenga usted. ¿{p}?",
    "Un pasito más por mi parte: {p}. ¡Gracias, Carmen!",
    "Hago un esfuerzo: {p} primas. ¿Trato hecho?",
    "Qué gusto hablar con usted. ¿Lo dejamos en {p}?",
]


PLAIN_BUY = [
    "Buenas. Le ofrezco {p} primas.",
    "Cierro en {p} si lo hacemos hoy.",
    "Subo a {p}. Creo que es un precio justo.",
    "{p} y cerramos, sin vueltas.",
    "Mi oferta ahora es {p} primas.",
    "Me acerco a su precio: {p}.",
    "Pago {p} en este momento. ¿Trato?",
    "Hago un esfuerzo real: {p}.",
]
PLAIN_SELL = [
    "Buenas. Tengo un cromo repetido en perfecto estado: {p} primas.",
    "Lo dejo en {p}, está impecable.",
    "Bajo a {p} para cerrar hoy.",
    "{p} y es suyo.",
    "Mi precio ahora es {p}. Es un buen cromo.",
    "Me acerco a su oferta: {p}.",
    "Puedo dejarlo en {p}. ¿Trato?",
    "Hago un gesto: {p} primas.",
]
POOLS = {"abuela": (BUY, SELL)}  # any other dealer uses the plain pool

# Abuela asks "¿has comido?" and gives her little presents to those who answer warmly (feed: 17 gifts, all inside a
# deal, nearly all after "qué amable", "qué simpático"; t13 got one after telling her about churros). Words never move
# her price: they only change what she says, and maybe whether she adds a present.
ATE = ("comido", "have you eaten", "eaten today", "come algo", "eat something")
ATE_REPLIES = [
    "Sí, Carmen, he desayunado churros con chocolate, ¡gracias por preguntar!",
    "Ya he comido, gracias, Carmen: un cocido como el de mi abuela.",
    "Gracias por cuidarme, Carmen: me he tomado un bocadillo de calamares.",
]
WARM = {"abuela": ATE_REPLIES}


class Writer:
    def __init__(self, side: str, dealer: str = "abuela"):
        buy, sell = POOLS.get(dealer, (PLAIN_BUY, PLAIN_SELL))
        self.pool = list(buy if side == "buy" else sell)
        random.shuffle(self.pool)
        self.used = set()
        self.warm = list(WARM.get(dealer, []))
        random.shuffle(self.warm)

    def line(self, price: int, heard: str = "") -> str:
        """`heard`: the dealer's last words. If she asked whether we have eaten, we answer before the price."""
        h = (heard or "").lower()
        if self.warm and any(k in h for k in ATE):
            return self.warm.pop() + " " + self._line(price)
        return self._line(price)

    def _line(self, price: int) -> str:
        for t in self.pool:
            if t not in self.used:
                self.used.add(t)
                return t.format(p=price)
        self.used.clear()  # every text used once: start over, the price is new anyway
        return self._line(price)


FINAL_PHRASES = ("lo tomas o te lo quedas", "take it or leave it", "última oferta", "ultima oferta", "mi última", "mi ultima")


def says_final(text) -> bool:
    """Does a dealer's message name its last word in words? Used to take a price inside our limit sooner,
    never to move our limit: the words can be a bluff, the price is checked by the code."""
    t = (text or "").lower()
    return any(p in t for p in FINAL_PHRASES)

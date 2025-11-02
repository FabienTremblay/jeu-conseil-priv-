# packages/cabinet/moteur/rng.py
import random, hashlib

class RngFacade:
    def __init__(self, seed: int):
        self._master = random.Random(seed)
        self._streams = {}

    def stream(self, name: str):
        if name not in self._streams:
            h = int(hashlib.sha256((str(self._master.random())+name).encode()).hexdigest(), 16) % (2**31-1)
            self._streams[name] = random.Random(h)
        return self._streams[name]

    def choice_weighted(self, items, weights, *, name="generic"):
        total = float(sum(weights))
        r = self.stream(name).random() * total
        acc = 0.0
        for it, w in zip(items, weights):
            acc += float(w)
            if r <= acc:
                return it
        return items[-1]

    def shuffle_inplace(self, seq, *, name="generic"):
        self.stream(name).shuffle(seq)


import math
import time
from collections import deque
from threading import Lock


def _agora():
    return time.monotonic()


class LimitadorAtendimentoIA:
    def __init__(self, maximo=5, janela=60, max_ips=10000):
        self.maximo = maximo
        self.janela = janela
        self.max_ips = max_ips
        self._historico = {}
        self._lock = Lock()

    def consumir(self, ip):
        agora = _agora()

        with self._lock:
            # Remove registros vencidos de todos os IPs.
            for chave in list(self._historico):
                fila = self._historico[chave]
                while fila and agora - fila[0] >= self.janela:
                    fila.popleft()
                if not fila:
                    del self._historico[chave]

            if ip not in self._historico:
                if len(self._historico) >= self.max_ips:
                    return self.janela
                self._historico[ip] = deque()

            fila = self._historico[ip]

            if len(fila) >= self.maximo:
                restante = self.janela - (agora - fila[0])
                return max(1, math.ceil(restante))

            fila.append(agora)
            return None

    def limpar_para_testes(self):
        with self._lock:
            self._historico.clear()


limitador_atendimento_ia = LimitadorAtendimentoIA()

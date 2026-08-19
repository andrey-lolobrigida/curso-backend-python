"""Bloco 3 — refatorar. ATENÇÃO: este arquivo tem código quebrado DE PROPÓSITO.

Este módulo foi "convertido para async" do jeito que a maioria das conversões
reais sai: async def em tudo, bloqueio por dentro. Conserte — e, para uma das
três funções, o conserto certo é deixar de ser async.
"""

import json
import time
from pathlib import Path

CONFIG = Path(__file__).with_name("config.json")

# Calibrado para ~1s na máquina do autor. Ajuste se aí for muito diferente.
VOLTAS_DE_CPU = 30_000_000


async def carregar_config() -> dict:
    """Roda uma vez, na subida do processo, sem ninguém na fila atrás."""
    return json.loads(CONFIG.read_text())


async def buscar(item_id: int) -> dict:
    """Finge uma consulta a um serviço externo — I/O de rede, espera pura."""
    time.sleep(0.3)
    return {"id": item_id, "nome": f"item {item_id}"}


async def resumo_pesado() -> int:
    """Puro CPU: nenhuma espera, só trabalho."""
    return sum(i * i for i in range(VOLTAS_DE_CPU))

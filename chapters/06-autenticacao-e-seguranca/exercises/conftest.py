"""Exercícios do capítulo 6. Nenhum bloco usa banco, nem importa `app/`: tudo em memória.

Este arquivo não tem fixture nenhuma, e mesmo assim precisa existir. Como a pasta não tem
`__init__.py`, o pytest põe a pasta de um conftest.py no `sys.path` antes de importar os
testes. É isso que faz o `from bloco1.login import entrar` funcionar.
"""

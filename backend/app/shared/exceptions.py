class KovirException(Exception):
    """Excecao base para erros controlados do Kovir."""

    pass


class NotFoundException(KovirException):
    """Erro usado quando um recurso nao e encontrado."""

    pass

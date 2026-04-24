from celery import shared_task


@shared_task
def squad_digest_friday() -> None:
    """
    Пятничный дайджест отряда (17:00).
    """
    # TODO: собрать статистику по отрядам и разослать дайджест
    return None


@shared_task
def curator_report_monday() -> None:
    """
    Понедельничный отчёт кураторам (09:00).
    """
    # TODO: сформировать отчёт по рисковым студентам и динамике рейтинга
    return None


from celery import shared_task


@shared_task
def check_badges_weekly() -> None:
    """
    Еженедельная проверка нашивок (прогон условий).
    """
    # TODO: обойти пользователей, проверить условия и выдать нашивки
    return None


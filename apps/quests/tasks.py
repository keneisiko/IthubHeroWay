from celery import shared_task


@shared_task
def send_daily_quest() -> None:
    """
    Ежедневная отправка квеста (07:30).
    """
    # TODO: выбрать/сгенерировать квест и разослать через уведомления/бота
    return None


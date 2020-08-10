import time

from notifypy import Notify


def get_timestamp():
    return int(round(time.time() * 1000))


def send_desktop_notification(message):
    notification = Notify()
    notification.application_name = 'pyfilesync'
    notification.title = 'File updated'
    notification.message = message
    notification.send()


def graceful_exit(status=0):
    print('Exiting.')
    exit(status)

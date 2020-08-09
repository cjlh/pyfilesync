import time
import socket

from notifypy import Notify


def get_timestamp():
    return int(round(time.time() * 1000))


def send_desktop_notification(message):
    notification = Notify()
    notification.title = 'pyfilesync'
    notification.message = message
    notification.send()


def graceful_exit(status=0):
    print('Exiting.')
    exit(status)


def recv_all(sock):
    data = ''
    continue_recv = True

    while continue_recv:
        try:
            data += sock.recv(1024)
        except socket.error as e:
            if e.errno != errno.EWOULDBLOCK:
                raise
            # If e.errno is errno.EWOULDBLOCK, then no more data
            continue_recv = False

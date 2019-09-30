"""
Circusd integration.

Hooks to manage service dependencies.
"""

import threading
import time


def send_command(f, *args):
    """
    Use a thread to send a command to circus.

    If we just send the command, circus gives an error that it is already
    starting / stopping watchers. This gives it some time to finish that before
    our command hit it.
    """

    def _send_command(f, *args):
        for _ in range(5):
            time.sleep(1.0)
            try:
                f(*args)
                break

            # TODO: Not sure that this is the best way to to detect failure.
            except:
                pass

    t = threading.Thread(target=_send_command, args=(f, ) + args)
    t.start()


def after_spawn(watcher, arbiter, hook_name, **kwargs):
    """
    Called after spwaning libreoffice.

    Starts the HTTP server.
    """
    watcher = arbiter.get_watcher('server')
    send_command(watcher.start)
    return True


# NOTE: this caused flapping and is no longer used.
def before_stop(watcher, arbiter, hook_name, **kwargs):
    """
    Called before stopping libreoffice.

    Stops the HTTP server.
    """
    watcher = arbiter.get_watcher('server')
    send_command(watcher.stop)
    return True

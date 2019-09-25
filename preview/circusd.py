import subprocess


def send_command(cmd_name, watcher):
    # Don't wait or you deadlock.
    subprocess.Popen([
        'circusctl', '--timeout=30', '--endpoint=tcp://127.0.0.1:5555',
        cmd_name, watcher
    ])


def after_start(watcher, arbiter, hook_name, **kwargs):
    send_command('start', 'server')
    return True


def before_stop(watcher, arbiter, hook_name, **kwargs):
    send_command('stop', 'server')
    return True

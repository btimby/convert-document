from easy_circus.client import Client


def send_command(cmd_name, watcher):
    print('Sending %s to %s' % (cmd_name, watcher))
    client = Client(host='127.0.0.1', port=5555, timeout=15)
    cmd = getattr(client, cmd_name)
    if not callable(cmd):
        raise ValueError('Invalid cmd_name %s' % cmd_name)
    cmd(watcher=watcher)


def after_start(watcher, arbiter, hook_name, **kwargs):
    send_command('start', 'server')
    return True


def before_stop(watcher, arbiter, hook_name, **kwargs):
    send_command('stop', 'server')
    return True

import logging
import subprocess

LOG = logging.getLogger(__name__)


def run_command(*args, input=None):
    '''Run a command, capturing stdout and stderr.

    If input is not None it is provided as stdin to the called
    process. Raise subprocess.CalledProcessError if the command exits
    with a nonzero exit code.
    '''

    cli = [str(arg) for arg in args]
    LOG.debug('running command: %s', ' '.join(cli))
    if input is not None:
        LOG.debug('with input: %s', repr(input))

    return subprocess.run(cli,
                          check=True,
                          stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE,
                          input=input)

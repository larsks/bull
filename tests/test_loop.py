import subprocess
from unittest import TestCase, mock

from bull import loop


class FakeCompletedProcess():
    def __init__(self, stdout=None, stderr=None, returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


@mock.patch('subprocess.run')
class TestMapperTables(TestCase):

    def test_create(self, mock_run):
        mock_run.return_value = FakeCompletedProcess(stdout=b'/dev/loop0')
        loop.LoopDevice.create('/does/not/exist')
        mock_run.assert_called_with(
            ['losetup', '--find', '--show', '/does/not/exist'],
            check=True, input=None, stderr=-1, stdout=-1)

    def test_remove(self, mock_run):
        mock_run.return_value = FakeCompletedProcess(stdout=b'/dev/loop0')
        dev = loop.LoopDevice.create('/does/not/exist')
        dev.remove()
        mock_run.assert_called_with(
            ['losetup', '-d', '/dev/loop0'],
            check=True, input=None, stderr=-1, stdout=-1)

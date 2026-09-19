import os

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')


@pytest.fixture(scope='session')
def app():
    from qtpy6 import QtWidgets
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

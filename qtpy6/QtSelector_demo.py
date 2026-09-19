"""Shows what a Qt program started from this session gets - run it after a change in QtSelector."""
import sys

import qtpy6
from qtpy6 import QtWidgets

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
lines = [f'scaled(100) = {qtpy6.scaled(100)}']  # first: resolves QT_SCALE when it is 'auto'
lines[:0] = [f'{name} = {getattr(qtpy6, name)}'
             for name in ('API_NAME', 'QT_VERSION', 'QT_SCALE', 'QT_FONT', 'QT_FONT_SIZE')]
label = QtWidgets.QLabel('\n'.join(lines))
label.set_margin(qtpy6.scaled(20))
label.set_window_title('qtpy6 settings')
label.show()
sys.exit(app.exec())

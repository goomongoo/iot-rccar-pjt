# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'form.ui'
##
## Created by: Qt User Interface Compiler version 6.10.1
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QLabel, QMainWindow, QMenuBar,
    QPlainTextEdit, QPushButton, QSizePolicy, QStatusBar,
    QWidget)

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(800, 600)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(MainWindow.sizePolicy().hasHeightForWidth())
        MainWindow.setSizePolicy(sizePolicy)
        MainWindow.setMinimumSize(QSize(800, 600))
        MainWindow.setMaximumSize(QSize(800, 600))
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")

        self.goBtn = QPushButton(self.centralwidget)
        self.goBtn.setObjectName(u"goBtn")
        self.goBtn.setGeometry(QRect(140, 300, 91, 51))
        font = QFont()
        font.setPointSize(9)
        self.goBtn.setFont(font)

        self.brakeBtn = QPushButton(self.centralwidget)
        self.brakeBtn.setObjectName(u"brakeBtn")
        self.brakeBtn.setGeometry(QRect(240, 300, 91, 51))
        self.brakeBtn.setFont(font)

        self.label = QLabel(self.centralwidget)
        self.label.setObjectName(u"label")
        self.label.setGeometry(QRect(20, 37, 141, 37))
        self.label.setFont(font)

        self.label_2 = QLabel(self.centralwidget)
        self.label_2.setObjectName(u"label_2")
        self.label_2.setGeometry(QRect(410, 37, 141, 37))
        self.label_2.setFont(font)

        self.commandTable = QPlainTextEdit(self.centralwidget)
        self.commandTable.setObjectName(u"commandTable")
        self.commandTable.setGeometry(QRect(20, 75, 371, 213))

        self.sensingTable = QPlainTextEdit(self.centralwidget)
        self.sensingTable.setObjectName(u"sensingTable")
        self.sensingTable.setGeometry(QRect(410, 75, 371, 213))

        self.modeSwitchBtn = QPushButton(self.centralwidget)
        self.modeSwitchBtn.setObjectName(u"modeSwitchBtn")
        self.modeSwitchBtn.setGeometry(QRect(410, 300, 371, 51))
        self.modeSwitchBtn.setFont(font)

        self.midBtn = QPushButton(self.centralwidget)
        self.midBtn.setObjectName(u"midBtn")
        self.midBtn.setGeometry(QRect(140, 362, 91, 51))
        self.midBtn.setFont(font)

        self.backBtn = QPushButton(self.centralwidget)
        self.backBtn.setObjectName(u"backBtn")
        self.backBtn.setGeometry(QRect(140, 425, 91, 51))
        self.backBtn.setFont(font)

        self.rightBtn = QPushButton(self.centralwidget)
        self.rightBtn.setObjectName(u"rightBtn")
        self.rightBtn.setGeometry(QRect(240, 362, 91, 51))
        self.rightBtn.setFont(font)

        self.leftBtn = QPushButton(self.centralwidget)
        self.leftBtn.setObjectName(u"leftBtn")
        self.leftBtn.setGeometry(QRect(40, 362, 91, 51))
        self.leftBtn.setFont(font)

        self.startBtn = QPushButton(self.centralwidget)
        self.startBtn.setObjectName(u"startBtn")
        self.startBtn.setGeometry(QRect(690, 12, 91, 51))
        self.startBtn.setFont(font)

        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(MainWindow)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 800, 26))
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName(u"statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.retranslateUi(MainWindow)

        self.goBtn.clicked.connect(MainWindow.go)
        self.brakeBtn.clicked.connect(MainWindow.brake)
        self.midBtn.clicked.connect(MainWindow.mid)
        self.backBtn.clicked.connect(MainWindow.back)
        self.leftBtn.clicked.connect(MainWindow.left)
        self.rightBtn.clicked.connect(MainWindow.right)
        self.startBtn.clicked.connect(MainWindow.start)

        self.modeSwitchBtn.clicked.connect(MainWindow.toggle_mode)

        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"GUI Remote Controller", None))
        self.goBtn.setText(QCoreApplication.translate("MainWindow", u"Go", None))
        self.brakeBtn.setText(QCoreApplication.translate("MainWindow", u"BRAKE", None))  # ✅ 추가
        self.label.setText(QCoreApplication.translate("MainWindow", u"command Table", None))
        self.label_2.setText(QCoreApplication.translate("MainWindow", u"sensing Table", None))
        self.midBtn.setText(QCoreApplication.translate("MainWindow", u"Mid", None))
        self.backBtn.setText(QCoreApplication.translate("MainWindow", u"Back", None))
        self.rightBtn.setText(QCoreApplication.translate("MainWindow", u"Right", None))
        self.leftBtn.setText(QCoreApplication.translate("MainWindow", u"Left", None))
        self.startBtn.setText(QCoreApplication.translate("MainWindow", u"START", None))

        self.modeSwitchBtn.setText(QCoreApplication.translate("MainWindow", u"Switch to Gesture Mode", None))
    # retranslateUi


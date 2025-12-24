# main.py
import sys
import argparse
from PySide6.QtWidgets import QApplication
from mainwindow import MainWindow


def parse_args():
    parser = argparse.ArgumentParser(description="GUI Remote Controller")
    parser.add_argument(
        "--broker",
        type=str,
        required=True,
        help="MQTT broker IP address (required)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    app = QApplication(sys.argv)
    w = MainWindow(broker_ip=args.broker)
    w.show()
    sys.exit(app.exec())

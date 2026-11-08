from __future__ import annotations
import argparse
import sys
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description="Dkord native desktop music player and Mashup Studio")
    parser.add_argument("--data-dir",type=Path,help="Developer/test user-data directory; normal installations use the stable per-user path")
    parser.add_argument("--self-test",action="store_true",help="Run actual native codec/renderer/widget smoke checks without any external provider")
    args=parser.parse_args()
    from PyQt6.QtCore import QLockFile
    from PyQt6.QtWidgets import QApplication,QMessageBox
    from platformdirs import user_data_path
    from .store import Store
    from .ui import MainWindow
    app=QApplication(sys.argv[:1]);app.setOrganizationName("Dkord");app.setOrganizationDomain("app.dkord");app.setApplicationName("Dkord")
    if args.self_test:
        from .selftest import run
        return run(app)
    root=args.data_dir or user_data_path("Dkord","Dkord",roaming=False)
    root.mkdir(parents=True,exist_ok=True)
    lock=QLockFile(str(root/"application.lock"));lock.setStaleLockTime(0)
    if not lock.tryLock(0):
        QMessageBox.information(None,"Dkord is already running","Close the existing Dkord window before opening this user-data library in another process.")
        return 1
    try:
        window=MainWindow(Store(root));window.show();result=app.exec()
        if window.restart_after_close:
            # closeEvent has cancelled work. Finish its bounded cleanup/SQLite writes
            # before another process can acquire the user-data library.
            window.pool.waitForDone();window.download_pool.waitForDone()
        lock.unlock()
        if window.restart_after_close:window.restart_after_close()
        return result
    except Exception as error:
        QMessageBox.critical(None,"Dkord could not open this library",str(error)+"\nExisting data has not been reset or deleted.")
        lock.unlock();return 1


if __name__=="__main__":
    raise SystemExit(main())

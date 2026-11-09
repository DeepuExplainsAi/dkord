from __future__ import annotations
import argparse
import sys
from pathlib import Path


def capture_ui(app, output, gallery=False):
    if gallery:
        from .gallery import capture_gallery as capture
    else:
        from .capture import capture
    # An error report belongs only to a new/empty capture destination. Never
    # overwrite an existing user's capture-error.txt or add files to their library.
    fresh=not output.exists() or (output.is_dir() and not output.is_symlink() and not any(output.iterdir()))
    try:
        return capture(app,output)
    except Exception:
        import traceback
        if fresh:
            try:
                output.mkdir(parents=True,exist_ok=True)
                with (output/'capture-error.txt').open('x',encoding='utf-8') as report:report.write(traceback.format_exc())
            except OSError:
                pass
        return 1


def main():
    parser=argparse.ArgumentParser(description="Dkord native desktop music player and Mashup Studio")
    parser.add_argument("--data-dir",type=Path,help="Developer/test user-data directory; normal installations use the stable per-user path")
    parser.add_argument("--self-test",action="store_true",help="Run actual native codec/renderer/widget smoke checks without any external provider")
    capture_options=parser.add_mutually_exclusive_group()
    capture_options.add_argument("--capture-gallery",type=Path,help="Capture all native pages/dialogs with clearly labelled isolated offline fixtures")
    capture_options.add_argument("--capture-ui",type=Path,help="Capture the actual window using isolated generated audio, never normal user data")
    parser.add_argument("--verify-upgrade-fixture",type=Path,help="Verify an existing isolated installer QA seed without resetting data; refuse normal libraries")
    args=parser.parse_args()
    from .qt import QLockFile, QApplication, QMessageBox, Qt, BINDING
    from platformdirs import user_data_path
    from .store import Store
    from .ui import MainWindow
    if BINDING=="PyQt5":
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling,True)
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps,True)
    app=QApplication(sys.argv[:1]);app.setOrganizationName("Dkord");app.setOrganizationDomain("app.dkord");app.setApplicationName("Dkord")
    if args.capture_gallery:
        return capture_ui(app,args.capture_gallery,gallery=True)
    if args.capture_ui:
        return capture_ui(app,args.capture_ui)
    if args.self_test:
        from .selftest import run
        return run(app)
    root=args.data_dir or user_data_path("Dkord","Dkord",roaming=False)
    if args.verify_upgrade_fixture:
        from .upgrade_fixture import run_probe
        return run_probe(root,args.verify_upgrade_fixture)
    root.mkdir(parents=True,exist_ok=True)
    lock=QLockFile(str(root/"application.lock"));lock.setStaleLockTime(0)
    if not lock.tryLock(0):
        QMessageBox.information(None,"Dkord is already running","Close the existing Dkord window before opening this user-data library in another process.")
        return 1
    try:
        window=MainWindow(Store(root));window.show();result=app.exec()
        # closeEvent cancelled work. Drain every owner before the data lock can
        # move to another process, including Home/artwork/dated-release tasks.
        for pool in (window.pool,window.download_pool,window.home_pool,window.artwork_cache.pool):
            pool.waitForDone()
        lock.unlock()
        if window.restart_after_close:window.restart_after_close()
        return result
    except Exception as error:
        QMessageBox.critical(None,"Dkord could not open this library",str(error)+"\nExisting data has not been reset or deleted.")
        lock.unlock();return 1


if __name__=="__main__":
    raise SystemExit(main())

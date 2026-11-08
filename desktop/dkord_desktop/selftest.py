"""Executed by each real packaged native binary. No remote providers, demo catalogue or credentials."""
import json
import platform
import tempfile
import threading
import wave
from pathlib import Path
from .media import MediaLibrary, probe
from .store import Store


def run(app) -> int:
    from .ui import MainWindow
    app.setQuitOnLastWindowClosed(False)
    with tempfile.TemporaryDirectory(prefix="dkord-native-smoke-") as folder:
        root=Path(folder);input=root/"codec-fixture.wav"
        with wave.open(str(input),"wb") as file:
            file.setnchannels(1);file.setsampwidth(2);file.setframerate(44100);file.writeframes(b"\0\0"*44100)
        store=Store(root/"data");library=MediaLibrary(store);project=store.create_project("Native codec smoke")
        library.import_source(project,input,threading.Event());output=library.export(project,threading.Event());file=library.local_file(output)
        assert file and 900<=probe(file)<=1100
        window=MainWindow(store,autoload=False);window.show();app.processEvents()
        assert window.isVisible() and window.windowTitle().startswith("Dkord")
        window.navigate("Mashup Studio");app.processEvents();assert window.heading.text()=="Mashup Studio"
        window.close();app.processEvents()
        print(json.dumps({"native_smoke":"PASS","os":platform.system(),"cpu":platform.machine(),"aac_duration_ms":probe(file),"native_widgets":True,"network_used":False}))
    return 0

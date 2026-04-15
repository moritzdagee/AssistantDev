"""
setup.py — baut die Assistant.app aus src/app.py
Ausführen: python3 setup.py py2app
"""
from setuptools import setup

APP = ['src/app.py']

OPTIONS = {
    'argv_emulation': False,
    'plist': {
        'LSUIElement': True,               # Nur Menu Bar, kein Dock-Icon
        'CFBundleName': 'Assistant',
        'CFBundleDisplayName': 'Assistant',
        'CFBundleIdentifier': 'com.moritz.assistant',
        'CFBundleVersion': '2.0.0',
        'CFBundleShortVersionString': '2.0',
        'NSAppleEventsUsageDescription': 'Für Apple Mail Integration.',
        'NSDesktopFolderUsageDescription': 'Für Zugriff auf Dateien.',
        'NSDocumentsFolderUsageDescription': 'Für Zugriff auf Dokumente.',
        'NSDownloadsFolderUsageDescription': 'Für Zugriff auf Downloads.',
    },
    'packages': ['rumps'],
    'resources': [
        'src/web_server.py',
        'src/email_watcher.py',
        'src/web_clipper_server.py',
    ],
    'includes': [],
    'excludes': ['tkinter', 'PyQt5', 'wx'],
}

setup(
    app=APP,
    name='Assistant',
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)

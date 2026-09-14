"""Load Study Helper runtime fixes for normal Python launches."""
try:
    from studyhelper_runtime import install
    install()
except Exception:
    # Never prevent Python itself from starting because an optional app patch
    # could not be installed. The frozen build also executes this file as a
    # PyInstaller runtime hook.
    pass

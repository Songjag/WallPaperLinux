python -m PyInstaller \
    --onefile \
    --windowed \
    --name DesktopLiveLinux \
    --add-data "data:data" \
    --paths "." \
    --collect-submodules src \
    --collect-all customtkinter \
    main.py

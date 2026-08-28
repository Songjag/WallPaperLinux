python -m PyInstaller \
    --onefile \
    --windowed \
    --name HyprWall \
    --add-data "data:data" \
    --paths "." \
    --collect-submodules src \
    --collect-all customtkinter \
    --collect-all yt_dlp \
    --hidden-import PIL._tkinter_finder \
    main.py

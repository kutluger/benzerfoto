"""`python -m benzerfoto` ile komut satırı aracını çalıştırır."""

import multiprocessing

from benzerfoto.cli import main

if __name__ == "__main__":
    # PyInstaller ile paketlenmiş EXE'de çok çekirdekli işleme için gerekli
    multiprocessing.freeze_support()
    raise SystemExit(main())

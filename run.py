import os
import sys
from pathlib import Path

from bili_garb_id_spider.interactive import main


def application_directory() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


if __name__ == "__main__":
    os.chdir(application_directory())
    main()

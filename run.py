import os
from pathlib import Path

from bili_garb_id_spider.interactive import main


if __name__ == "__main__":
    os.chdir(Path(__file__).resolve().parent)
    main()

from optiontrader.core import Core
from dotenv import load_dotenv

if __name__ == '__main__':
    load_dotenv()
    core = Core()
    core.connect()
    core.start()

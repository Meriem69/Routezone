"""
Configuration du logger pour l'API RouteZone.
Ecrit les logs a la fois dans la console et dans logs/api.log
"""
import logging
from pathlib import Path

# Creer le dossier logs/ s'il n'existe pas
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "api.log"

# Format des logs : timestamp | niveau | nom_module | message
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logger(name: str = "routezone") -> logging.Logger:
    """
    Cree un logger configure pour l'API.
    
    - Niveau INFO par defaut (ne logue pas les DEBUG)
    - Ecrit en console ET dans logs/api.log
    - Format : 2026-05-10 13:52:14 | INFO     | routezone | message
    """
    logger = logging.getLogger(name)
    
    # Si le logger est deja configure, ne le re-configure pas (evite les doublons)
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.INFO)
    
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    
    # Handler 1 : ecrire dans la console (terminal)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Handler 2 : ecrire dans le fichier logs/api.log
    file_handler = logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger


# Logger global pour toute l'API
logger = setup_logger("routezone")
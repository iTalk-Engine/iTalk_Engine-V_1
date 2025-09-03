import logging
from logging.handlers import RotatingFileHandler

def setup(engine):
    # On va créer un logger plus complet que le logger de base
    # Avec rotation des fichiers pour pas que ça pète à force d'écrire
    log_file = engine.config.get("advanced_log_file", "advanced_engine.log")
    max_bytes = engine.config.get("advanced_log_max_bytes", 2_000_000)
    backup_count = engine.config.get("advanced_log_backup_count", 3)
    log_level_str = engine.config.get("advanced_log_level", "INFO").upper()
    log_level = getattr(logging, log_level_str, logging.INFO)

    # On récupère le logger ItalkEngine ou on le crée
    logger = logging.getLogger("ItalkEngine")
    logger.setLevel(log_level)

    # Si y'a déjà des handlers, on les vire pour éviter les doublons
    if logger.hasHandlers():
        logger.handlers.clear()

    # On met le handler qui gère la rotation des fichiers
    handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8"
    )

    # On met un format simple mais clair pour les logs
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
    handler.setFormatter(formatter)

    # On attache le handler au logger
    logger.addHandler(handler)

    # On remplace le logger de base du moteur par ce logger avancé
    engine.logger = logger

    # Petit message pour confirmer que tout est bien lancé
    engine.logger.info(f"Advanced logging activé, fichier : {log_file}")

"""
Ce programme est en charge de communiquer avec l'Arduino pour acquérir les données du moteur en 
fonction des consignes de PWM et de durée fournies par le programme dataset_generation.py.
On veut récupérer et stocker en temps réel les mesures de courant, de vitesse du moteur, et la 
consigne MLI qui lui a été envoyée. Celles-ci doivent être sauvegardées dans un fichier CSV 
pour chaque essai, avec un nom de fichier unique basé sur la date et l'heure de l'acquisition.
Le programme doit également gérer les erreurs de communication avec l'Arduino et s'assurer 
que le moteur est correctement arrêté entre les essais pour éviter toute interférence entre les mesures.
"""

import argparse
import csv
from datetime import datetime
import math
from pathlib import Path
import sys
import time

try:
    import serial
except ImportError:
    serial = None

if __package__:
    from ..convertir_csv_v3 import VREF, RESOLUTION, GAIN_COURANT, GAIN_VITESSE
else:
    # Le convertisseur partagé reste dans le dossier Python parent.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from convertir_csv_v3 import VREF, RESOLUTION, GAIN_COURANT, GAIN_VITESSE

def verif_port():
    ports = serial.tools.list_ports.comports()

    for port in ports:
        print(port.device, "-", port.description)

        if "Arduino" in port.description:
            return port.device

    raise RuntimeError("Aucune carte Arduino détectée")

PORT = verif_port()
BAUD = 115200
TOP = 799
F_CLK = 16_000_000
N_DEC = 50  # une conversion toutes les 4,99375 ms, chaque grandeur à ~100 Hz
MAX_COMMANDES = 64
MAX_DUREE_MS = 60_000
DELAI_COMMUNICATION_S = 2.0
DOSSIER_MESURES = Path(__file__).resolve().parent / "csv" / "echantillons"
IDENTIFICATION = f"PRET,ECHANTILLON,1,{TOP},{N_DEC},{MAX_COMMANDES},{MAX_DUREE_MS}"
COLONNES = [
    "temps_s", "grandeur", "valeur_brute", "courant_A", "vitesse_rad_s",
    "commande_index", "pwm_consigne_pct", "pwm_valeur", "pwm_pct", "date",
]


def _valider_commandes(commandes):
    """Retourne (durée_ms, PWM demandée, OCR1B, durée en périodes MLI)."""
    commandes = list(commandes)
    if not 1 <= len(commandes) <= MAX_COMMANDES:
        raise ValueError(f"Il faut entre 1 et {MAX_COMMANDES} commandes par essai.")
    resultat = []
    for numero, commande in enumerate(commandes, start=1):
        if not isinstance(commande, (tuple, list)) or len(commande) != 2:
            raise ValueError(f"Commande {numero} : couple (duree_ms, pwm_pct) attendu.")
        duree, pwm = commande
        if type(duree) is not int or not 1 <= duree <= MAX_DUREE_MS:
            raise ValueError(f"Commande {numero} : durée entière entre 1 et {MAX_DUREE_MS} ms attendue.")
        if (isinstance(pwm, bool) or not isinstance(pwm, (int, float))
                or not math.isfinite(pwm) or not 0 <= pwm <= 100):
            raise ValueError(f"Commande {numero} : PWM finie entre 0 et 100 % attendue.")
        # Arrondi par excès au BOTTOM suivant, identique au programme Arduino.
        periodes = (duree * (F_CLK // 1000) + 2 * TOP - 1) // (2 * TOP)
        resultat.append((duree, pwm, round(TOP * pwm / 100), periodes))
    if sum(commande[0] for commande in resultat) > MAX_DUREE_MS:
        raise ValueError(f"La durée totale de l'essai ne doit pas dépasser {MAX_DUREE_MS} ms.")
    return resultat


class _LiaisonArduino:
    """Protocole ASCII borné ; conserve aussi les lignes reçues par fragments."""

    def __init__(self, connexion):
        self.connexion = connexion
        self.tampon = bytearray()

    def envoyer(self, message):
        donnees = (message + "\n").encode("ascii")
        if self.connexion.write(donnees) != len(donnees):
            raise RuntimeError("Écriture série incomplète.")

    def lire(self, delai=DELAI_COMMUNICATION_S):
        echeance = time.monotonic() + delai
        while time.monotonic() < echeance:
            self.tampon.extend(self.connexion.read_until(b"\n", size=128))
            if len(self.tampon) > 127:
                raise RuntimeError("Ligne Arduino trop longue.")
            if self.tampon.endswith(b"\n"):
                donnees = bytes(self.tampon)
                self.tampon.clear()
                try:
                    ligne = donnees.decode("ascii").rstrip("\r\n")
                except UnicodeDecodeError as erreur:
                    raise RuntimeError("Octets série invalides.") from erreur
                if ligne.startswith("ERR,"):
                    raise RuntimeError(f"Erreur Arduino : {ligne}")
                return ligne
        raise RuntimeError("Délai dépassé : aucune ligne Arduino complète reçue.")

    def attendre(self, attendu):
        reponse = self.lire()
        if reponse != attendu:
            raise RuntimeError(f"Réponse Arduino inattendue : {reponse!r}, attendu {attendu!r}.")

    def arreter(self):
        self.envoyer("0")  # également compris par l'ancien CMD_data.ino
        echeance = time.monotonic() + DELAI_COMMUNICATION_S
        while time.monotonic() < echeance:
            ligne = self.lire(echeance - time.monotonic())
            if ligne in ("ARRET", "Nouveau OCR1B = 0"):
                return
            # Des mesures déjà transmises peuvent précéder l'accusé d'arrêt.
        raise RuntimeError("L'arrêt du moteur n'a pas été confirmé par l'Arduino.")


def _recevoir_mesures(liaison, fichier, commandes, date_acquisition):
    ecrivain = csv.writer(fichier)
    ecrivain.writerow(COLONNES)
    fichier.flush()
    total_periodes = sum(commande[3] for commande in commandes)
    nombre_attendu = (total_periodes - 1) // N_DEC + 1
    echeance = time.monotonic() + total_periodes * 2 * TOP / F_CLK + DELAI_COMMUNICATION_S
    nombre = 0
    indice = 0
    fin_palier = commandes[0][3]
    while True:
        restant = echeance - time.monotonic()
        if restant <= 0:
            raise RuntimeError("Durée maximale de réception dépassée.")
        champs = liaison.lire(min(DELAI_COMMUNICATION_S, restant)).split(",")
        if champs[0] == "FIN":
            try:
                if len(champs) != 3:
                    raise ValueError
                recus, perdus = map(int, champs[1:])
            except ValueError as erreur:
                raise RuntimeError("Fin de transmission invalide.") from erreur
            if perdus != 0 or recus != nombre or nombre != nombre_attendu:
                raise RuntimeError(
                    f"Acquisition incomplète : {nombre}/{nombre_attendu} mesures, "
                    f"compteur Arduino {recus}, pertes {perdus}."
                )
            return nombre
        try:
            if len(champs) != 6 or champs[0] != "M":
                raise ValueError
            tick, canal, brut, numero, pwm = map(int, champs[1:])
        except ValueError as erreur:
            raise RuntimeError(f"Mesure Arduino invalide : {','.join(champs)!r}.") from erreur
        if (tick != nombre * N_DEC or tick >= total_periodes
                or canal != nombre % 2 or not 0 <= brut <= RESOLUTION):
            raise RuntimeError("Mesure incohérente : temps, alternance ADC ou valeur brute invalide.")
        while tick >= fin_palier:
            indice += 1
            fin_palier += commandes[indice][3]
        if numero != indice + 1 or pwm != commandes[indice][2]:
            raise RuntimeError("La consigne mesurée ne correspond pas à la séquence envoyée.")
        courant = brut * VREF / RESOLUTION / GAIN_COURANT if canal == 0 else ""
        vitesse = brut * VREF / RESOLUTION / GAIN_VITESSE if canal == 1 else ""
        ecrivain.writerow([
            f"{tick * 2 * TOP / F_CLK:.9f}", "courant" if canal == 0 else "vitesse",
            brut, courant, vitesse, numero, commandes[indice][1], pwm,
            f"{100 * pwm / TOP:.6f}", date_acquisition,
        ])
        fichier.flush()  # conserve les données déjà reçues si la liaison se coupe
        nombre += 1


def acquisition_echantillon(commandes, fichier_sortie=None, *, port=PORT, baud=BAUD,
                            repos_s=2.0, delai_demarrage_s=2.0, serial_factory=None):
    """Exécute une séquence et retourne le chemin du CSV créé.

    Nécessite Arduino/CMD_echantillon/CMD_echantillon.ino sur une Mega 2560.
    Chaque couple est (durée entière en ms, PWM en %). L'Arduino enchaîne les
    paliers sans pause ; le repos n'a lieu qu'avant l'essai complet. Le CSV
    contient une ligne par conversion alternée, avec une seule des colonnes
    courant_A/vitesse_rad_s remplie : leurs instants sont distincts.

    Sans fichier_sortie, le nom contient date, heure et microsecondes. Un chemin
    fourni est respecté et jamais écrasé. En cas d'erreur, le CSV partiel reste
    disponible ; l'arrêt est demandé et le port fermé avant de remonter l'erreur.
    L'arrêt physique ne peut pas être garanti si la liaison est déconnectée ;
    l'Arduino coupe aussi la PWM de façon autonome en fin de séquence.
    """
    commandes = _valider_commandes(commandes)
    for nom, valeur in (("repos_s", repos_s), ("delai_demarrage_s", delai_demarrage_s)):
        if not isinstance(valeur, (int, float)) or not math.isfinite(valeur) or valeur < 0:
            raise ValueError(f"{nom} doit être un nombre fini positif ou nul.")
    if fichier_sortie is None:
        fichier_sortie = DOSSIER_MESURES / f"essai_{datetime.now():%Y%m%d_%H%M%S_%f}.csv"
    fichier_sortie = Path(fichier_sortie)
    factory = getattr(serial, "Serial", None) if serial_factory is None else serial_factory
    if not callable(factory):
        raise RuntimeError("La bibliothèque pyserial est requise : python -m pip install pyserial. "
                           "Le paquet nommé serial seul ne fournit pas la liaison série.")
    fichier_sortie.parent.mkdir(parents=True, exist_ok=True)
    with fichier_sortie.open("x", newline="", encoding="utf-8") as fichier:
        connexion = None
        liaison = None
        try:
            connexion = factory(port=port, baudrate=baud, timeout=0.2, write_timeout=1.0)
            liaison = _LiaisonArduino(connexion)
            time.sleep(delai_demarrage_s)
            connexion.reset_input_buffer()
            liaison.arreter()
            liaison.envoyer("ID")
            try:
                liaison.attendre(IDENTIFICATION)
            except RuntimeError as erreur:
                raise RuntimeError(
                    "Programme Arduino incompatible ou absent. Téléverser "
                    "Arduino/CMD_echantillon/CMD_echantillon.ino sur la Mega 2560."
                ) from erreur
            time.sleep(repos_s)
            liaison.envoyer(f"SEQ,{len(commandes)}")
            liaison.attendre("OK,SEQ")
            for numero, (duree, _, pwm, _) in enumerate(commandes, start=1):
                liaison.envoyer(f"C,{duree},{pwm}")
                liaison.attendre(f"OK,C,{numero}")
            date_acquisition = datetime.now().isoformat(timespec="microseconds")
            liaison.envoyer("GO")
            liaison.attendre(f"DEBUT,{TOP},{N_DEC},{len(commandes)}")
            nombre = _recevoir_mesures(liaison, fichier, commandes, date_acquisition)
        except BaseException as erreur:
            erreur.add_note(f"CSV éventuellement partiel : {fichier_sortie}")
            raise
        finally:
            erreur_initiale = sys.exc_info()[1]
            erreurs_fermeture = []
            if connexion is not None:
                try:
                    if liaison is not None:
                        liaison.arreter()
                except Exception as erreur:
                    erreurs_fermeture.append(f"Arrêt du moteur non confirmé : {erreur}")
                finally:
                    try:
                        connexion.close()
                    except Exception as erreur:
                        erreurs_fermeture.append(f"Fermeture du port impossible : {erreur}")
            if erreurs_fermeture:
                message = "; ".join(erreurs_fermeture)
                if erreur_initiale is not None:
                    erreur_initiale.add_note(message)
                else:
                    raise RuntimeError(message)
    print(f"{nombre} mesures enregistrées dans {fichier_sortie}")
    return fichier_sortie


if __name__ == "__main__":
    parseur = argparse.ArgumentParser(description="Acquisition d'une séquence PWM sur Arduino Mega.")
    parseur.add_argument("--commande", nargs=2, type=int, action="append", required=True,
                         metavar=("DUREE_MS", "PWM_PCT"), help="Répéter pour ajouter des paliers.")
    parseur.add_argument("--sortie", type=Path, help="CSV de sortie (nom daté par défaut).")
    parseur.add_argument("--port", default=PORT)
    args = parseur.parse_args()
    try:
        acquisition_echantillon(args.commande, args.sortie, port=args.port)
    except (ValueError, RuntimeError, OSError) as erreur:
        parseur.exit(1, f"Erreur : {erreur}\n")

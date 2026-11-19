"""Simulation de la vraie chaîne Python/sketch, sans port série physique.

L'exécutable C++ inclut le sketch Arduino ; les ticks sont accélérés et les
valeurs ADC sont synthétiques. Ce banc ne simule pas les cycles CPU AVR.
"""

import argparse
from bisect import bisect_right
from contextlib import redirect_stdout
import csv
from datetime import datetime
import io
import json
from pathlib import Path
import random
import subprocess
import time

from Python.dataset_generation_V2 import acquisition_echantillon as acquisition
from Python.dataset_generation_V2 import dataset_generation as campagne


class ArduinoSurPC:
    def __init__(self, executable, *, fragments=False, panne=None):
        self.processus = subprocess.Popen(
            [str(executable), "--simulate-serial"], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="ascii", bufsize=1,
        )
        self.tampon = bytearray()
        self.fragments = fragments
        self.panne = panne
        self.panne_declenchee = False
        self.deconnecte = False
        self.nombre_mesures = 0
        self.pwm = 0
        self.actif = False
        self.tick = 0
        self.ferme = False
        self.commandes_envoyees = []

    def _echanger(self, requete):
        self.processus.stdin.write(requete + "\n")
        self.processus.stdin.flush()
        entete = self.processus.stdout.readline(128).strip().split(",")
        if len(entete) != 4:
            raise RuntimeError(f"Simulateur arrêté : {entete}")
        taille, self.pwm, actif, self.tick = map(int, entete)
        self.actif = bool(actif)
        reponse = bytearray()
        while len(reponse) < taille:
            fragment = self.processus.stdout.read(taille - len(reponse))
            if not fragment:
                raise RuntimeError("Réponse du simulateur tronquée.")
            reponse.extend(fragment.encode("ascii"))
        return reponse

    def write(self, donnees):
        if self.deconnecte:
            raise OSError("Déconnexion USB simulée")
        commande = donnees.decode("ascii").strip()
        self.commandes_envoyees.append(commande)
        self.tampon.extend(self._echanger("SEND " + commande))
        return len(donnees)

    def read_until(self, delimiteur=b"\n", size=128):
        if self.deconnecte:
            raise OSError("Déconnexion USB simulée")
        if self.panne == "silence" and self.panne_declenchee:
            return b""
        if self.nombre_mesures >= 5 and not self.panne_declenchee and self.panne:
            self.panne_declenchee = True
            if self.panne == "deconnexion":
                self.deconnecte = True
                raise OSError("Déconnexion USB simulée")
            if self.panne == "saturation":
                self._echanger("STALL 10000")
            if self.panne == "silence":
                return b""
        if not self.tampon:
            reponse = self._echanger("READ")
            if reponse.startswith(b"M,"):
                self.nombre_mesures += 1
                if self.panne_declenchee and self.panne == "ligne_perdue":
                    self.panne = None  # une seule suppression
                    return self.read_until(delimiteur, size)
                if self.panne_declenchee and self.panne == "adc_invalide":
                    champs = reponse.decode("ascii").strip().split(",")
                    champs[3] = "1024"
                    reponse = (",".join(champs) + "\n").encode("ascii")
                    self.panne = None
            self.tampon.extend(reponse)
        if not self.tampon:
            return b""
        fin = self.tampon.find(delimiteur)
        taille = min(len(self.tampon) if fin < 0 else fin + 1, size)
        if self.fragments:
            taille = min(taille, 3)
        resultat = bytes(self.tampon[:taille])
        del self.tampon[:taille]
        return resultat

    def reset_input_buffer(self):
        self.tampon.clear()

    def close(self):
        if self.ferme:
            return
        try:
            if self.deconnecte:
                # Instrumentation interne : le PC n'envoie plus de commandes.
                # L'ADC poursuit son travail jusqu'à l'arrêt autonome du sketch.
                self._echanger("STALL 10000")
            self.processus.stdin.close()
            self.processus.wait(timeout=5)
            assert self.processus.returncode == 0, "Arrêt anormal du simulateur"
        finally:
            if self.processus.poll() is None:
                self.processus.kill()
                self.processus.wait(timeout=5)
            self.processus.stdout.close()
            self.processus.stderr.close()
            self.ferme = True


def verifier_csv(chemin, commandes):
    fins = []
    for duree, _ in commandes:
        # Durées quantifiées en périodes de 1598 cycles à 16 MHz.
        fins.append((fins[-1] if fins else 0) + (16000 * duree + 1597) // 1598)
    with chemin.open(newline="", encoding="utf-8") as fichier:
        lignes = list(csv.DictReader(fichier))
    assert len(lignes) == (fins[-1] + 49) // 50, "Nombre de mesures incorrect"
    for index, ligne in enumerate(lignes):
        tick = index * 50
        commande = bisect_right(fins, tick)
        pwm_pct = commandes[commande][1]
        pwm = round(799 * pwm_pct / 100)
        assert abs(float(ligne["temps_s"]) - tick * 1598 / 16e6) < 1e-9
        assert int(ligne["commande_index"]) == commande + 1
        assert float(ligne["pwm_consigne_pct"]) == pwm_pct
        assert int(ligne["pwm_valeur"]) == pwm
        assert abs(float(ligne["pwm_pct"]) - 100 * pwm / 799) < 1e-6
        courant = index % 2 == 0
        brut = 123 if courant else 456
        assert int(ligne["valeur_brute"]) == brut
        colonne = "courant_A" if courant else "vitesse_rad_s"
        autre = "vitesse_rad_s" if courant else "courant_A"
        gain = acquisition.GAIN_COURANT if courant else acquisition.GAIN_VITESSE
        assert abs(float(ligne[colonne]) - brut * acquisition.VREF / acquisition.RESOLUTION / gain) < 1e-12
        assert ligne[autre] == ""
        assert ligne["grandeur"] == ("courant" if courant else "vitesse")
        datetime.fromisoformat(ligne["date"])
    return len(lignes)


def ecrire_rapport(dossier, rapport):
    (dossier / "rapport.json").write_text(json.dumps(rapport, ensure_ascii=False, indent=2), encoding="utf-8")
    lignes = [
        "# Résultat de la simulation Python / Arduino", "",
        f"Exécution : {rapport['date']}. Graine aléatoire : {rapport['graine']}.", "",
        f"Durée réelle du banc : {rapport['duree_execution_s']} s. "
        f"Connexions fermées avec PWM finale nulle : {rapport['connexions_fermees_pwm_nulle']}.", "",
        "| Scénario | Résultat | Mesures écrites |",
        "| --- | --- | ---: |",
    ]
    for scenario in rapport["scenarios"]:
        nombre = scenario.get("mesures", scenario.get("mesures_conservees", 0))
        lignes.append(f"| {scenario['scenario']} | {scenario['statut']} | {nombre} |")
    lignes.extend([
        "", "La campagne complète produit 100 CSV. Pour chaque ligne, le banc vérifie "
        "le temps, le canal, la valeur ADC, la conversion physique, le numéro de commande et la PWM.", "",
        "Les erreurs attendues interrompent l'acquisition et conservent le CSV partiel. "
        "Lors de la déconnexion USB, le PC signale que l'arrêt n'a pas pu être confirmé ; "
        "l'instrumentation du simulateur vérifie séparément l'arrêt autonome du sketch.", "",
        f"Limites : {rapport['limites']}", "",
        "Les repos et le délai de démarrage sont désactivés pour accélérer le banc. "
        "Le test ne valide ni les délais série physiques, ni la précision ADC, ni la réponse mécanique du moteur.", "",
        "[Données détaillées](rapport.json) · [CSV de la campagne](campagne_complete/) · "
        "[Journal](campagne.log)", "",
    ])
    (dossier / "rapport.md").write_text("\n".join(lignes), encoding="utf-8")


def simuler(executable, dossier):
    dossier.mkdir(parents=True, exist_ok=False)
    debut = time.perf_counter()
    ports = []
    resultats = []

    def acquerir(commandes, fichier_sortie, **options):
        arduino = ArduinoSurPC(executable, **options)
        ports.append(arduino)
        try:
            return acquisition.acquisition_echantillon(
                commandes, fichier_sortie, repos_s=0, delai_demarrage_s=0,
                serial_factory=lambda **kwargs: arduino,
            )
        finally:
            if not arduino.ferme:
                arduino.close()
            assert arduino.pwm == 0 and not arduino.actif, "Le sketch n'a pas arrêté la PWM"

    # Campagne complète : générateur et acquisition de production.
    random.seed(20261119)
    journal = io.StringIO()
    with redirect_stdout(journal):
        campagne_dir = campagne.lancer_campagne(
            campagne.ParametresCampagne(nb_echantillons=100),
            dossier / "campagne_complete", acquisition_fn=acquerir,
        )
    (dossier / "campagne.log").write_text(journal.getvalue(), encoding="utf-8")
    with (campagne_dir / "consignes.csv").open(newline="", encoding="utf-8") as fichier:
        sequences = []
        for ligne in csv.reader(fichier):
            valeurs = list(map(int, ligne))
            assert len(valeurs) == 2 * valeurs[0] + 1
            sequences.append(list(zip(valeurs[1::2], valeurs[2::2])))
    fichiers = sorted((campagne_dir / "mesures").glob("*.csv"))
    assert len(fichiers) == len(sequences) == 100
    mesures = sum(verifier_csv(chemin, commandes) for chemin, commandes in zip(fichiers, sequences))
    duree_ms = sum(duree for commandes in sequences for duree, _ in commandes)
    resultats.append({"scenario": "campagne_100_essais", "statut": "OK", "csv": 100,
                      "mesures": mesures, "duree_consignes_s": duree_ms / 1000})

    for nom, commandes, options in (
        ("minimum_1ms_pwm0", [(1, 0)], {}),
        ("maximum_60s_pwm100", [(60000, 100)], {}),
        ("maximum_64_commandes", [(1, 100 if n % 2 else 0) for n in range(64)], {}),
        ("paliers_plus_courts_que_echantillonnage", [(1, 0), (1, 50), (20, 100)], {}),
        ("pwm_decimale", [(20, 33.3), (30, 66.6)], {}),
        ("serie_fragmentee", [(100, 20), (200, 60)], {"fragments": True}),
    ):
        chemin = dossier / f"{nom}.csv"
        with redirect_stdout(journal):
            acquerir(commandes, chemin, **options)
        nombre = verifier_csv(chemin, commandes)
        resultats.append({"scenario": nom, "statut": "OK", "mesures": nombre})

    for panne in ("ligne_perdue", "adc_invalide", "saturation", "deconnexion", "silence"):
        chemin = dossier / f"panne_{panne}.csv"
        try:
            acquerir([(1000, 50)], chemin, panne=panne)
        except (RuntimeError, OSError) as erreur:
            with chemin.open(newline="", encoding="utf-8") as fichier:
                conservees = len(list(csv.DictReader(fichier)))
            assert conservees > 0, "Les mesures déjà reçues ont été perdues"
            resultats.append({"scenario": panne, "statut": "ERREUR_ATTENDUE",
                              "mesures_conservees": conservees, "erreur": str(erreur),
                              "notes": getattr(erreur, "__notes__", [])})
        else:
            raise AssertionError(f"Panne {panne} non détectée")

    assert all(port.ferme and port.pwm == 0 and not port.actif for port in ports)
    rapport = {"date": datetime.now().isoformat(), "graine": 20261119,
               "duree_execution_s": round(time.perf_counter() - debut, 3),
               "scenarios": resultats, "connexions_fermees_pwm_nulle": len(ports),
               "limites": "Simulation logique accélérée du vrai sketch ; ADC synthétiques ; aucune émulation des cycles AVR ou du moteur physique."}
    ecrire_rapport(dossier, rapport)
    print(json.dumps(rapport, ensure_ascii=False, indent=2))
    return rapport


if __name__ == "__main__":
    depot = Path(__file__).resolve().parents[3]
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("--executable", type=Path,
                         default=depot / "build/arduino-validation/cmd_echantillon_logic_test.exe")
    parseur.add_argument("--dossier", type=Path,
                         default=depot / "build" / f"simulation_echantillon_{datetime.now():%Y%m%d_%H%M%S_%f}")
    args = parseur.parse_args()
    simuler(args.executable.resolve(), args.dossier.resolve())

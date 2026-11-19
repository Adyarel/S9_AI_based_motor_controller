"""Acquisition avec port série simulé, sans démarrer de moteur."""

from collections import deque
import csv
from datetime import datetime
import io
from contextlib import redirect_stdout
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from Python.dataset_generation_V2 import acquisition_echantillon as acquisition
from Python.dataset_generation_V2 import dataset_generation as campagne


class ArduinoSimule:
    def __init__(self, *, transformer=None, fragments=False, transcript=None):
        self.reponses = deque()
        self.commandes = []
        self.ecritures = []
        self.ferme = False
        self.transformer = transformer
        self.fragments = fragments
        self.transcript = transcript
        self.verifier_fin = None

    def reset_input_buffer(self):
        self.reponses.clear()

    def ajouter(self, texte):
        self.reponses.append((texte + "\n").encode("ascii"))

    def write(self, donnees):
        texte = donnees.decode("ascii").strip()
        self.ecritures.append(texte)
        if texte == "0":
            self.reponses.clear()
            self.ajouter("ARRET")
        elif texte == "ID":
            self.ajouter(acquisition.IDENTIFICATION)
        elif texte.startswith("SEQ,"):
            self.commandes = []
            self.ajouter("OK,SEQ")
        elif texte.startswith("C,"):
            _, duree, pwm = texte.split(",")
            self.commandes.append((int(duree), int(pwm)))
            self.ajouter(f"OK,C,{len(self.commandes)}")
        elif texte == "GO":
            if self.transcript is not None:
                for ligne in self.transcript.splitlines():
                    self.ajouter(ligne)
            else:
                self.ajouter(f"DEBUT,799,50,{len(self.commandes)}")
                ticks = [math.ceil(duree * 16000 / 1598) for duree, _ in self.commandes]
                indice = 0
                fin = ticks[0]
                nombre = 0
                for tick in range(0, sum(ticks), 50):
                    while tick >= fin:
                        indice += 1
                        fin += ticks[indice]
                    self.ajouter(f"M,{tick},{nombre % 2},{100 + nombre},{indice + 1},{self.commandes[indice][1]}")
                    nombre += 1
                self.ajouter(f"FIN,{nombre},0")
        if self.transformer:
            self.transformer(self, texte)
        return len(donnees)

    def read_until(self, delimiteur=b"\n", size=128):
        if not self.reponses:
            return b""
        ligne = self.reponses.popleft()
        if ligne.startswith(b"FIN,") and self.verifier_fin:
            self.verifier_fin()
        limite = min(size, 3) if self.fragments else size
        if len(ligne) > limite:
            self.reponses.appendleft(ligne[limite:])
            return ligne[:limite]
        return ligne

    def close(self):
        self.ferme = True


class AcquisitionTests(unittest.TestCase):
    def setUp(self):
        racine = Path(__file__).resolve().parents[3] / "build" / "dataset-validation"
        racine.mkdir(parents=True, exist_ok=True)
        temporaire = tempfile.TemporaryDirectory(dir=racine)
        self.addCleanup(temporaire.cleanup)
        self.racine = Path(temporaire.name)
        self.sortie = self.racine / "essai.csv"
        self.commandes = [(20, 25), (30, 75)]
        sortie = redirect_stdout(io.StringIO())
        sortie.__enter__()
        self.addCleanup(sortie.__exit__, None, None, None)

    def lancer(self, arduino, commandes=None, **options):
        return acquisition.acquisition_echantillon(
            self.commandes if commandes is None else commandes,
            self.sortie, repos_s=0, delai_demarrage_s=0,
            serial_factory=lambda **kwargs: arduino, **options,
        )

    def lignes(self):
        with self.sortie.open(newline="", encoding="utf-8") as fichier:
            return list(csv.DictReader(fichier))

    def test_sequence_csv_temps_conversions_et_arret(self):
        arduino = ArduinoSimule()
        arduino.verifier_fin = lambda: self.assertEqual(len(self.lignes()), 11)
        self.assertEqual(self.lancer(arduino), self.sortie)
        lignes = self.lignes()
        self.assertEqual(len(lignes), 11)
        self.assertEqual(arduino.ecritures, ["0", "ID", "SEQ,2", "C,20,200", "C,30,599", "GO", "0"])
        self.assertTrue(arduino.ferme)
        for index, ligne in enumerate(lignes):
            self.assertAlmostEqual(float(ligne["temps_s"]), index * 50 * 1598 / 16e6)
            colonne = "courant_A" if index % 2 == 0 else "vitesse_rad_s"
            autre = "vitesse_rad_s" if index % 2 == 0 else "courant_A"
            gain = acquisition.GAIN_COURANT if index % 2 == 0 else acquisition.GAIN_VITESSE
            self.assertAlmostEqual(float(ligne[colonne]), (100 + index) * 5 / 1023 / gain)
            self.assertEqual(ligne[autre], "")
            self.assertEqual(int(ligne["commande_index"]), 1 if index < 5 else 2)
            self.assertEqual(float(ligne["pwm_consigne_pct"]), 25 if index < 5 else 75)
            datetime.fromisoformat(ligne["date"])

    def test_lignes_fragmentaires(self):
        self.lancer(ArduinoSimule(fragments=True))
        self.assertEqual(len(self.lignes()), 11)

    def test_paliers_courts_sans_mesure_sur_certains_paliers(self):
        self.lancer(ArduinoSimule(), [(1, 0), (1, 50), (20, 100)])
        lignes = self.lignes()
        self.assertEqual(lignes[0]["pwm_valeur"], "0")
        self.assertEqual(lignes[1]["commande_index"], "3")
        self.assertEqual(lignes[1]["pwm_valeur"], "799")

    def test_donnees_invalides_preservent_csv_et_ferment_port(self):
        for fautif in (
            b"M,50,1,1024,1,200\n", b"M,51,1,100,1,200\n",
            b"M,50,0,100,1,200\n", b"M,50,1,100,2,599\n",
            b"M,50,1,100,1,201\n", b"M,x,1,100,1,200\n",
            b"ERR,tampon\n", b"\xff\n", b"x" * 128 + b"\n",
        ):
            with self.subTest(fautif=fautif):
                self.sortie = self.racine / f"erreur_{len(list(self.racine.iterdir()))}.csv"

                def modifier(arduino, texte):
                    if texte == "GO":
                        arduino.reponses[2] = fautif

                arduino = ArduinoSimule(transformer=modifier)
                with self.assertRaises(RuntimeError):
                    self.lancer(arduino)
                self.assertEqual(len(self.lignes()), 1)
                self.assertEqual(arduino.ecritures[-1], "0")
                self.assertTrue(arduino.ferme)

    def test_fin_invalide_ou_mesures_perdues(self):
        for fin in (b"FIN,11,1\n", b"FIN,10,0\n", b"FIN,11\n", b"FIN,x,0\n"):
            with self.subTest(fin=fin):
                self.sortie = self.racine / f"fin_{len(list(self.racine.iterdir()))}.csv"

                def modifier(arduino, texte):
                    if texte == "GO":
                        arduino.reponses[-1] = fin

                arduino = ArduinoSimule(transformer=modifier)
                with self.assertRaises(RuntimeError):
                    self.lancer(arduino)
                self.assertTrue(arduino.ferme)

    def test_firmware_incompatible(self):
        def modifier(arduino, texte):
            if texte == "ID":
                arduino.reponses[-1] = b"ANCIEN_FIRMWARE\n"

        arduino = ArduinoSimule(transformer=modifier)
        with self.assertRaisesRegex(RuntimeError, "Téléverser"):
            self.lancer(arduino)
        self.assertNotIn("GO", arduino.ecritures)
        self.assertTrue(arduino.ferme)

    def test_refus_ecrasement_avant_ouverture_port(self):
        self.sortie.write_text("original", encoding="utf-8")
        with patch.object(acquisition.serial, "Serial", create=True) as factory:
            with self.assertRaises(FileExistsError):
                acquisition.acquisition_echantillon(self.commandes, self.sortie)
        factory.assert_not_called()
        self.assertEqual(self.sortie.read_text(encoding="utf-8"), "original")

    def test_commandes_invalides_avant_ouverture_port(self):
        for commandes in (
            [], [(0, 10)], [(True, 10)], [(1.5, 10)], [(1, -1)], [(1, 101)],
            [(1, float("nan"))], [(1, float("inf"))], [(1, True)],
            [(1, 20, 30)], [(30001, 10), (30000, 20)], [(1, 10)] * 65,
        ):
            with self.subTest(commandes=commandes):
                with patch.object(acquisition.serial, "Serial", create=True) as factory:
                    with self.assertRaises(ValueError):
                        acquisition.acquisition_echantillon(commandes, self.sortie)
                factory.assert_not_called()
        self.assertFalse(self.sortie.exists())

    def test_rupture_serie_et_keyboard_interrupt(self):
        for erreur in (OSError("câble débranché"), KeyboardInterrupt()):
            with self.subTest(erreur=type(erreur).__name__):
                self.sortie = self.racine / f"rupture_{type(erreur).__name__}.csv"

                def modifier(arduino, texte):
                    if texte == "GO":
                        raise erreur

                arduino = ArduinoSimule(transformer=modifier)
                with self.assertRaises(type(erreur)):
                    self.lancer(arduino)
                self.assertEqual(arduino.ecritures[-1], "0")
                self.assertTrue(arduino.ferme)

    def test_erreur_arret_ne_masque_pas_erreur_initiale(self):
        def modifier(arduino, texte):
            if texte == "GO":
                raise OSError("coupure initiale")
            if texte == "0" and "GO" in arduino.ecritures:
                raise OSError("arrêt impossible")

        arduino = ArduinoSimule(transformer=modifier)
        with self.assertRaisesRegex(OSError, "coupure initiale") as contexte:
            self.lancer(arduino)
        self.assertTrue(arduino.ferme)
        self.assertTrue(any("Arrêt du moteur non confirmé" in note for note in contexte.exception.__notes__))

    def test_arret_non_confirme_interdit_succes(self):
        def modifier(arduino, texte):
            if texte == "0" and "GO" in arduino.ecritures:
                raise OSError("arrêt impossible")

        arduino = ArduinoSimule(transformer=modifier)
        with self.assertRaisesRegex(RuntimeError, "Arrêt du moteur non confirmé"):
            self.lancer(arduino)
        self.assertTrue(arduino.ferme)

    def test_timeout_et_ecriture_incomplete(self):
        arduino = ArduinoSimule()
        liaison = acquisition._LiaisonArduino(arduino)
        with self.assertRaisesRegex(RuntimeError, "Délai dépassé"):
            liaison.lire(delai=0.001)
        with patch.object(arduino, "write", return_value=0):
            with self.assertRaisesRegex(RuntimeError, "incomplète"):
                liaison.envoyer("GO")

    def test_pyserial_absent_erreur_explicite(self):
        with patch.object(acquisition, "serial", None):
            with self.assertRaisesRegex(RuntimeError, "pyserial est requise"):
                acquisition.acquisition_echantillon(self.commandes, self.sortie)
        self.assertFalse(self.sortie.exists())

    def test_nom_date_par_defaut(self):
        arduino = ArduinoSimule()
        with patch.object(acquisition, "DOSSIER_MESURES", self.racine):
            chemin = acquisition.acquisition_echantillon(
                self.commandes, repos_s=0, delai_demarrage_s=0,
                serial_factory=lambda **kwargs: arduino,
            )
        self.assertRegex(chemin.name, r"^essai_\d{8}_\d{6}_\d{6}\.csv$")
        self.assertTrue(chemin.is_file())

    def test_integration_campagne_avec_vraie_fonction(self):
        ports = []

        def factory(**kwargs):
            arduino = ArduinoSimule()
            ports.append(arduino)
            return arduino

        def acquerir(commandes, fichier_sortie):
            return acquisition.acquisition_echantillon(
                commandes, fichier_sortie, repos_s=0, delai_demarrage_s=0,
                serial_factory=factory,
            )

        dossier = campagne.lancer_campagne(
            campagne.ParametresCampagne(nb_echantillons=2, commande_nb_min=2, commande_nb_max=2),
            self.racine, acquisition_fn=acquerir,
        )
        self.assertEqual(len(list((dossier / "mesures").glob("*.csv"))), 2)
        self.assertTrue(all(arduino.ferme for arduino in ports))
        self.assertIs(campagne.charger_acquisition(), acquisition.acquisition_echantillon)

    def test_transcript_du_programme_arduino_reel(self):
        executable = Path(__file__).resolve().parents[3] / "build" / "arduino-validation" / "cmd_echantillon_logic_test.exe"
        if not executable.is_file():
            self.skipTest("Compiler d'abord Arduino/tests/cmd_echantillon_logic_test.cpp.")
        resultat = subprocess.run([str(executable), "--transcript"], capture_output=True, text=True, timeout=10)
        self.assertEqual(resultat.returncode, 0, resultat.stderr)
        self.lancer(ArduinoSimule(transcript=resultat.stdout))
        self.assertEqual(len(self.lignes()), 11)

    def test_lancement_acquisition_script_et_module(self):
        depot = Path(__file__).resolve().parents[3]
        script = depot / "Python" / "dataset_generation_V2" / "acquisition_echantillon.py"
        for nom, arguments, repertoire in (
            ("script", [str(script)], self.racine),
            ("module", ["-m", "Python.dataset_generation_V2.acquisition_echantillon"], depot),
        ):
            with self.subTest(nom=nom):
                aide = subprocess.run(
                    [sys.executable, *arguments, "--help"], cwd=repertoire,
                    capture_output=True, text=True, timeout=15,
                )
                self.assertEqual(aide.returncode, 0, aide.stderr)
                self.assertIn("--commande", aide.stdout)
                # Une commande invalide doit être refusée sans ouvrir de port.
                invalide = subprocess.run(
                    [sys.executable, *arguments, "--commande", "0", "50",
                     "--sortie", str(self.sortie)], cwd=repertoire,
                    capture_output=True, text=True, timeout=15,
                )
                self.assertEqual(invalide.returncode, 1, invalide.stderr)
                self.assertNotIn("Traceback", invalide.stderr)
                self.assertFalse(self.sortie.exists())


if __name__ == "__main__":
    unittest.main()

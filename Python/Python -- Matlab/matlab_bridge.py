# ------------------------------------------------------------ #
# Date : 05/11/26
# Description : liaison Python <-> MATLAB / Simulink
#               (MATLAB Engine API for Python : Python pilote MATLAB)
#
#   envoyer(nom, valeur)   Python -> MATLAB : crée la variable dans le workspace
#   lire(nom)              MATLAB -> Python : récupère une variable du workspace
#   appeler(fonction, ...) appelle une fonction / un script MATLAB
#   envoyer_csv(chemin)    envoie un CSV converti (clean_csv_...) à MATLAB
#                          (variables : temps_courant, courant, temps_vitesse, vitesse, pwm_pct)
#   simuler(modele, duree) lance un modèle Simulink et récupère t et y
# ------------------------------------------------------------ #

# ------------------------------------------------------------ #
# Installation (une seule fois) :
#   1) MATLAB installé sur le PC. Noter sa version (R2024b, R2025a, ...).
#   2) Dans un terminal :   pip install matlabengine
#      Si pip refuse ou prend une version incompatible, installer depuis MATLAB :
#        cd "<matlabroot>/extern/engines/python"
#        python -m pip install .
#      (taper "matlabroot" dans MATLAB pour connaître <matlabroot>)
#   3) Vérifier que la version de Python est compatible avec la version de MATLAB
#      (tableau "Versions of Python Compatible with MATLAB" dans la doc MathWorks).
#
# Lancement :
#   python matlab_bridge.py                     test de la liaison
#   python matlab_bridge.py clean_csv_xxx.csv   test + envoi d'un CSV à MATLAB
#
# Utilisation dans un script :
#   from matlab_bridge import MatlabBridge
#   with MatlabBridge() as m:
#       m.envoyer("x", [1, 2, 3])
#       print(m.appeler("test_liaison", [1, 2, 3]))
#
# Session MATLAB déjà ouverte (pour voir les variables dans MATLAB) :
#   dans MATLAB :  matlab.engine.shareEngine
#   dans Python :  MatlabBridge(session="auto")
# ------------------------------------------------------------ #

# -------------------------Librairie---------------------------- #
import csv
import os
import sys

import numpy as np

# ---------------------------Paramètres--------------------------- #
SEPARATEUR = ","        # le même que dans acquisition_moteur.py
DOSSIER_MATLAB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "MatLab")


# ---------------------------Conversions-------------------------- #
def _vers_matlab(valeur):
    """Python -> type MATLAB. Les listes / tableaux numpy deviennent des vecteurs colonne."""
    import matlab
    if isinstance(valeur, bool):
        return valeur
    if isinstance(valeur, (int, float)):
        return float(valeur)
    if isinstance(valeur, str):
        return valeur
    tableau = np.asarray(valeur, dtype=float)
    if tableau.ndim == 0:
        return float(tableau)
    if tableau.ndim == 1:
        tableau = tableau.reshape(-1, 1)
    return matlab.double(tableau.tolist())


def _vers_python(valeur):
    """Type MATLAB -> float, str ou ndarray (vecteur 1D si la matrice est une ligne / colonne)."""
    if isinstance(valeur, (bool, int, float, str)) or valeur is None:
        return valeur
    if isinstance(valeur, tuple):
        return tuple(_vers_python(v) for v in valeur)
    tableau = np.array(valeur, dtype=float)
    if tableau.ndim == 2 and 1 in tableau.shape:
        tableau = tableau.ravel()
    return tableau


# ------------------------------CSV------------------------------- #
def lire_csv(chemin):
    """Lit un CSV converti (clean_csv_...) sans passer par MATLAB.

    Deux formats sont acceptés :
      - actuel : temps_courant_s, courant_A, temps_vitesse_s, vitesse_rad_s, pwm_valeur, pwm_pct, date
        (courant et vitesse sont mesurés en alternance : chaque grandeur a son propre temps)
      - ancien : temps_s, courant_A, vitesse_rad_s, ... (un seul temps pour les deux)

    Retourne un dictionnaire : temps_courant, courant, temps_vitesse, vitesse (tableaux numpy)
    et pwm_pct (float, si la colonne existe)."""
    with open(chemin, newline="", encoding="utf-8") as f:
        lecteur = csv.DictReader(f, delimiter=SEPARATEUR)
        colonnes = lecteur.fieldnames or []
        if "courant_brut" in colonnes:
            raise ValueError("ce fichier contient des valeurs brutes : "
                             "convertis-le d'abord avec convertir_csv.py")
        deux_temps = "temps_courant_s" in colonnes
        requises = (("temps_courant_s", "courant_A", "temps_vitesse_s", "vitesse_rad_s") if deux_temps
                    else ("temps_s", "courant_A", "vitesse_rad_s"))
        for colonne in requises:
            if colonne not in colonnes:
                raise ValueError(f"colonne '{colonne}' absente (colonnes trouvées : {colonnes})")
        lignes = list(lecteur)

    col = lambda nom: np.array([float(l[nom]) for l in lignes])
    temps_i = col("temps_courant_s" if deux_temps else "temps_s")
    temps_w = col("temps_vitesse_s") if deux_temps else temps_i
    donnees = {
        "temps_courant": temps_i,
        "courant": col("courant_A"),
        "temps_vitesse": temps_w,
        "vitesse": col("vitesse_rad_s"),
    }
    if lignes and "pwm_pct" in colonnes:
        donnees["pwm_pct"] = float(lignes[0]["pwm_pct"])
    return donnees


# ---------------------------Classe------------------------------- #
class MatlabBridge:
    """Liaison avec une session MATLAB.

    session=None     : démarre une nouvelle session MATLAB (une dizaine de secondes)
    session="auto"   : se connecte à la 1re session partagée (matlab.engine.shareEngine)
    session="nom"    : se connecte à la session partagée portant ce nom
    dossier_matlab   : dossier ajouté au path MATLAB (par défaut ../MatLab)
    """

    def __init__(self, session=None, dossier_matlab=DOSSIER_MATLAB, _moteur=None):
        if _moteur is not None:                 # moteur factice pour les tests sans MATLAB
            self.eng, self._possede = _moteur, True
        else:
            import matlab.engine
            if session is None:
                print("Démarrage de MATLAB ...")
                self.eng, self._possede = matlab.engine.start_matlab(), True
            else:
                nom = None if session == "auto" else session
                self.eng, self._possede = matlab.engine.connect_matlab(nom), False
            print("Connexion établie avec MATLAB")
        if dossier_matlab and os.path.isdir(dossier_matlab):
            self.eng.addpath(os.path.abspath(dossier_matlab), nargout=0)

    # ---- Python -> MATLAB
    def envoyer(self, nom, valeur):
        """Crée / remplace la variable <nom> dans le workspace MATLAB."""
        self.eng.workspace[nom] = _vers_matlab(valeur)

    # ---- MATLAB -> Python
    def lire(self, nom):
        """Retourne la variable <nom> du workspace MATLAB (float, str ou ndarray)."""
        return _vers_python(self.eng.workspace[nom])

    # ---- exécution
    def executer(self, code):
        """Exécute du code MATLAB, sans valeur de retour. Ex : executer("x = 2*y;")"""
        self.eng.eval(code, nargout=0)

    def appeler(self, fonction, *args, nargout=1):
        """Appelle une fonction MATLAB. Ex : appeler("sqrt", 16.0) ; appeler("max", v, nargout=2)"""
        resultat = getattr(self.eng, fonction)(*[_vers_matlab(a) for a in args], nargout=nargout)
        return _vers_python(resultat)

    # ---- données du moteur
    def envoyer_csv(self, chemin):
        """Lit un CSV converti et crée dans MATLAB : temps_courant, courant, temps_vitesse,
        vitesse (et pwm_pct)."""
        donnees = lire_csv(chemin)
        for nom, valeur in donnees.items():
            self.envoyer(nom, valeur)
        print(f"{len(donnees['temps_courant'])} points envoyés à MATLAB "
              f"(variables : {', '.join(donnees)})")
        return donnees

    # ---- Simulink
    def simuler(self, modele, duree, **variables):
        """Simule le modèle Simulink <modele> (sans .slx) pendant <duree> secondes.
        Les **variables sont d'abord envoyées au workspace (paramètres du modèle).
        Retourne (t, y) : y = signaux des blocs Out du modèle (format Array)."""
        for nom, valeur in variables.items():
            self.envoyer(nom, valeur)
        self.executer(f"load_system('{modele}'); "
                      f"set_param('{modele}', 'SaveFormat', 'Array'); "
                      f"out_sim = sim('{modele}', 'StopTime', '{duree}'); "
                      f"t_sim = out_sim.tout; y_sim = out_sim.yout;")
        return self.lire("t_sim"), self.lire("y_sim")

    # ---- fermeture
    def fermer(self):
        """Ferme MATLAB seulement si cette classe l'a démarré (pas une session partagée)."""
        if self._possede:
            self.eng.quit()
        self._possede = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.fermer()


# ----------------------------Lancement--------------------------- #
if __name__ == "__main__":
    with MatlabBridge() as m:
        # 1) Python -> MATLAB -> Python
        m.envoyer("x", [1, 2, 3])
        m.executer("y = x.^2;")
        print("y = x^2 calculé par MATLAB :", m.lire("y"))
        print("test_liaison([1 2 3]) :", m.appeler("test_liaison", [1, 2, 3]))

        # 2) Envoi d'un CSV du moteur (optionnel : python matlab_bridge.py fichier.csv)
        if len(sys.argv) > 1:
            m.envoyer_csv(sys.argv[1])
            m.executer("fprintf('MATLAB a reçu %d points, Te = %.6f s\\n', "
                       "numel(temps_courant), mean(diff(temps_courant)));")

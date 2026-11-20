Voici le code qui relie Python ↔ MATLAB/Simulink pour simuler le moteur et afficher le courant et la vitesse.

Principe : Python pilote MATLAB via la MATLAB Engine API. Python envoie la consigne PWM (%), MATLAB lance le modèle Simulink modele_moteur.slx, écrit un CSV dans simulations/, puis Python relit ce CSV et trace les courbes.

**Installation (une seule fois)

MATLAB + Simulink installés sur le PC.
Dans un terminal : pip install matlabengine matplotlib numpy
Vérifier que ta version de Python est compatible avec ta version de MATLAB 

**Utilisation

-Garder tous les fichiers dans le même dossier et lancer Python depuis ce dossier.
-Interface graphique : python graphic.py. On saisit le modèle (modele_moteur), la consigne PWM en % et la durée en s, puis on clique sur « Lancer Simulation ».
-En ligne de commande : python lancer_simulation.py modele_moteur 15 1.5 (PWM 15 %, durée 1,5 s).
-Les résultats sont enregistrés dans simulations/ (colonnes : temps_courant_s, courant_A, temps_vitesse_s, vitesse_rad_s, pwm_valeur, pwm_pct, date).

**Rôle des fichiers

-matlab_bridge.py : la liaison Python ↔ MATLAB (envoyer, lire, appeler, simuler).
-simuler_moteur.m : lance Simulink et écrit le CSV.
-lancer_simulation.py : enchaîne le tout (consigne → simulation → lecture du CSV).
-graphic.py : l’interface et les graphiques.
-modele_moteur.slx : le modèle Simulink. Il lit la variable pwm_pct, Out1 = courant (A), Out2 = vitesse (rad/s).

Note : Si tu as une autre version de MATLAB : le paquet matlabengine doit correspondre à ta version (version -release dans MATLAB). Par exemple, pip install matlabengine==24.2.* pour R2024b. Vérifie aussi que ta version de Python est compatible avec ta version de MATLAB
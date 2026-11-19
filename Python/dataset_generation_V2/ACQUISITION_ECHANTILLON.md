Acquisition d'une séquence de PWM
===============================

Utiliser Python 3.11 ou plus récent et installer la dépendance :

```powershell
python -m pip install pyserial==3.5
```

Le paquet nécessaire est `pyserial`. Le paquet distinct nommé `serial`, présent
dans l'environnement Python initial, sert à sérialiser des documents et ne
fournit pas `Serial`.

Téléverser `Arduino/CMD_echantillon/CMD_echantillon.ino` sur la Mega 2560 avant
les essais. La configuration PB6/OC1B, A9, ADC14 et ADC15 reprend le montage de
`CMD_data.ino`. Le moniteur série de l'IDE doit libérer le port avant Python.
Le port par défaut est `COM4`, à régler dans `acquisition_echantillon.py` pour
les campagnes, ou avec `--port` pour un essai manuel.

Exemple manuel, deux paliers successifs de 100 puis 200 ms :

```powershell
python Python/dataset_generation_V2/acquisition_echantillon.py --port COM4 --commande 100 20 --commande 200 60
```

Une campagne entière se lance avec :

```powershell
python Python/dataset_generation_V2/dataset_generation.py --nombre 5
```

La fonction `acquisition_echantillon(commandes, fichier_sortie)` accepte une
liste de couples `(duree_ms, pwm_pct)` et retourne le chemin du CSV créé.
L'Arduino reçoit toute la séquence avant le départ et enchaîne les paliers.
La durée de chaque palier est arrondie au multiple supérieur de la période
MLI, soit 99,875 µs. Limites : 64 commandes et 60 000 ms cumulées par essai.
Le repos de 2 secondes a lieu avant chaque essai complet, après confirmation
de PWM nulle ; la connexion série est fermée à la fin de chaque essai.

Le nom par défaut contient la date, l'heure et les microsecondes. Un chemin
explicitement fourni est respecté, avec création exclusive pour éviter les
écrasements. Les noms des fichiers de campagne incluent aussi cet horodatage.

Le CSV contient une ligne par conversion : temps depuis le début de l'essai,
grandeur, ADC brut, courant en A ou vitesse en rad/s, numéro de commande,
PWM demandée, OCR1B, PWM réellement quantifiée et date de l'acquisition.
Courant et vitesse sont alternés, espacés de 4,99375 ms : environ 100 Hz
par grandeur. La colonne de l'autre grandeur reste vide pour conserver les
instants propres à chaque capteur. Les gains sont importés de
`convertir_csv_v3.py`, y compris son gain de vitesse actuel de 0,5 V/(rad/s).

Chaque ligne est écrite et vidée vers le système de fichiers dès réception.
Une erreur conserve le CSV partiel et interrompt la campagne ; il faut donc
écarter l'essai interrompu de l'entraînement. Le code demande alors l'arrêt,
vérifie son accusé de réception et ferme le port. Une liaison déconnectée
empêche de confirmer l'arrêt physique. Le firmware coupe aussi la PWM de façon
autonome en fin de séquence ou si son tampon de transmission sature.

Validation depuis la racine du dépôt :

```powershell
& 'C:/msys64/ucrt64/bin/g++.exe' -std=c++17 -Wall -Wextra -Werror -O1 -D_GLIBCXX_ASSERTIONS Arduino/tests/cmd_echantillon_logic_test.cpp -o build/arduino-validation/cmd_echantillon_logic_test.exe
& './build/arduino-validation/cmd_echantillon_logic_test.exe'
python -m unittest discover -s Python/dataset_generation_V2/tests -v
```

Pour simuler une campagne complète de 100 essais avec la fonction Python de
production et le vrai sketch compilé sur PC, puis injecter des pannes :

```powershell
python -m Python.dataset_generation_V2.tests.simuler_campagne
```

Ce banc crée un dossier `build/simulation_echantillon_<date_heure>` contenant
les CSV, un journal et les rapports `rapport.md` / `rapport.json`. Les ticks
sont accélérés, avec des valeurs ADC synthétiques de 123 pour le courant et
456 pour la vitesse. Il teste aussi les durées et nombres de commandes limites,
les fragments série, les lignes perdues, une valeur ADC invalide, une saturation
du tampon, une déconnexion USB et un silence de la liaison.

Le banc C++ inclut le vrai sketch. Les tests Python couvrent aussi une
transmission produite par ce banc, et la campagne complète avec une liaison
simulée. Ces tests ne valident pas le matériel, les cycles CPU, la précision
ADC ou les délais physiques. Aucun téléversement ni essai moteur automatique
n'est effectué par les tests.

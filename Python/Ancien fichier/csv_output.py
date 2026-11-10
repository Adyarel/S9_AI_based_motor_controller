import serial
import time
import csv
import atexit

PORT = 'COM4'
BAUDRATE = 115200
DUREE_ACQUISITION_SEC = 5  # Durée de l'enregistrement après démarrage

# Initialisation de la connexion
arduino = serial.Serial(PORT, BAUDRATE, timeout=0.1)

def nettoyer_port():
    if arduino.is_open:
        arduino.write(b'A') # Sécurité : coupe le moteur avant de fermer
        arduino.close()
        print("\nPort fermé et moteur arrêté.")

atexit.register(nettoyer_port)

print("Attente du reset de l'Arduino (2s)...")
time.sleep(2)
arduino.reset_input_buffer() # Vide les potentiels messages parasites

print("Attente d'une seconde avant le lancement...")
time.sleep(1)

# Lancement du moteur
print("Lancement du moteur (Envoi 'D')")
arduino.write(b'D')
temps_debut_test = time.time()

# Création et ouverture du fichier CSV
with open('reponse_moteur.csv', mode='w', newline='') as fichier:
    writer = csv.writer(fichier)
    writer.writerow(["Temps(ms)", "Courant(Brut)", "Vitesse(Brut)"]) # En-tête
    
    print(f"Acquisition en cours pour {DUREE_ACQUISITION_SEC} secondes...")
    
    while (time.time() - temps_debut_test) < DUREE_ACQUISITION_SEC:
        if arduino.in_waiting > 0:
            # Lecture de la ligne série
            ligne = arduino.readline().decode('utf-8').strip()
            if ligne:
                donnees = ligne.split(',')
                # Vérification de l'intégrité de la trame (3 valeurs attendues)
                if len(donnees) == 3:
                    writer.writerow(donnees)

print("Acquisition terminée. Fin du script.")
# Le module atexit s'assurera d'envoyer 'A' et de faire arduino.close()
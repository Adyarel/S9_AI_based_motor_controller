import serial
import csv
import time

# Configuration du port serie (remplacer 'COM3' par le port de l'Arduino)
PORT = 'COM4'
BAUD_RATE = 115200
FICHIER_CSV = 'mesures_pc.csv'

# Connexion à l'Arduino
try:
    arduino = serial.Serial(PORT, BAUD_RATE, timeout=1)
    time.sleep(2) # Attente de l'initialisation de l'Arduino
    print(f"Connecté au port {PORT}")
except Exception as e:
    print(f"Erreur de connexion : {e}")
    exit()

# Ouverture du fichier CSV en mode écriture
with open(FICHIER_CSV, mode='w', newline='') as f:
    writer = csv.writer(f, delimiter=',')
    
    print("Acquisition en cours... (Ctrl+C pour arrêter)")
    try:
        while True:
            if arduino.in_waiting > 0:
                # Lecture de la ligne, décodage et suppression des sauts de ligne
                ligne = arduino.readline().decode('utf-8').strip()
                
                if ligne:
                    # Séparation des données par la virgule
                    donnees = ligne.split(',')
                    writer.writerow(donnees)
                    print(f"Enregistré : {donnees}")
                    
    except KeyboardInterrupt:
        print("\nAcquisition terminée.")
    finally:
        arduino.close()
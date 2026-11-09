# -*- coding: utf-8 -*-
"""
Éditeur de Spyder

Ceci est un script temporaire.
"""
import serial
import time
import serial.tools.list_ports

"""
Info : 
    
OCRA1 = 799.0
    
# Fermeture de la connexion
    arduino.close()    
    
"""

def verif_port():
    ports = serial.tools.list_ports.comports()
    for port in ports:
        print(port.device, "-", port.description)

arduino = serial.Serial('COM8', 115200, timeout=1)

print("Connexion établie")

time.sleep(2)

def modifier_OCR1B(valeur):
    # Envoi de la valeur
    arduino.write(f"{valeur}\n".encode())

    # Réception de la confirmation
    reponse = arduino.readline().decode().strip()

    print("OCR1B =", reponse)
   
def modifier_PWM(pourcentage):
    if not 0 <= pourcentage <= 100:
        print("Erreur : pourcentage hors limites")
        return

    valeur = round(799 * pourcentage / 100)

    modifier_OCR1B(valeur)

modifier_PWM(75)
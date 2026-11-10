# ------------------------------------------------------------ #
# Auteur : Brice, Ronan
# Date : 04/11/26
# Descritpion : communication arduino python comd PWm moteur
# ------------------------------------------------------------ #

# ------------------------------------------------------------ #
#lancé : python -i com_arduino_python.py
#Fermeture de la connexion : arduino.close() ou crtlZ puis entrée

#OCR1A = 799.0
# ------------------------------------------------------------ #

# -------------------------Librairie---------------------------- #
import serial
import time
import serial.tools.list_ports
import atexit

# ---------------------------Fonction----------------------------- #

# Fct : s'assurer connexion port serie carte
def verif_port():
    ports = serial.tools.list_ports.comports()
    for port in ports:
        print(port.device, "-", port.description)

arduino = serial.Serial('COM4', 115200, timeout=1)

print("Connexion établie avec Arduino")

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
    
def fermer_connexion():
    if arduino.is_open:
        # modifier_PWM(0)
        arduino.write(b'A')
        arduino.close()
        print("Port série fermé proprement et libéré pour l'IDE.")

# On enregistre cette fonction pour qu'elle s'exécute à la sortie du script
atexit.register(fermer_connexion)

modifier_PWM(25)
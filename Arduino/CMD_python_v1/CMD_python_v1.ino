// ----------------------------------------------------- //
// LOUINEAU Ronan - GE5
// 04/11/26
// Version 1.0 : objectif MLI moteur
// ----------------------------------------------------- //

// --------------------Librairie----------------------- //

#define T_h 0.0001  // T_hash = 100, micro sec
#define TN_h 799.0    // F_hash = 10khz
#define Fclkio 16000000.0

// --- Assignation des broches ---
const int PIN_ALIM = A9; // PK1 : tension fixe
const int PIN_CAPTEUR_COURANT = A14; // PK6 : Capteur courant (10 V/A)
const int PIN_CAPTEUR_VITESSE = A15; // PK7 : Capteur vitesse (1 V/rad/s)

// --- Paramètres d'échantillonnage et de conversion ---
const unsigned long PERIODE_ECHANTILLONNAGE_MS = 20; 

const float GAIN_COURANT = 10.0;   // 10 V/A
const float GAIN_VITESSE = 1.0;    // 1 V/rad/s

unsigned long tempsDepart = 0;
unsigned long prochainEchantillon = 0;
bool acquisitionActive = false;

float I = 0;
float Omega = 0;

void setup() {
  Serial.begin(115200);
  pinMode(PIN_ALIM, OUTPUT);
  digitalWrite(PIN_ALIM, LOW); 
  delay(500);
  digitalWrite(PIN_ALIM, HIGH);
  

  DDRB = 0xC0;  // pb7 et pb6 sortie, MLI sur OC1B = PB6 = patte 6
  DDRF = 0x00;  // port F en entrée : entrée analogique sur A0 = patte 8 de l'ATmega2560

  // configuration du timer 1
  TCCR1A = (1 << COM1B1) + (1 << WGM10);               // COM1B_1:0 = 11   -> mise a un sur egalite, WGM_13:10 = 1001 -> mode 9
  TCCR1B = (1 << ICNC1) + (1 << WGM13) + (1 << CS10);  // CS_12:10  = 001  -> prediv par 1
  OCR1A = TN_h;                                        // T_hash = 100 micros
  OCR1B = OCR1A / 2;                                   // V initial

  DDRA = 0x00;
  DDRC = 0x00;

}


void recevoirConsignePWM() {

    if (Serial.available() > 0) {

        String message = Serial.readStringUntil('\n');
        message.trim();

        // Vérification que le message n'est pas vide
        if (message.length() == 0) {
            return;
        }

        // Vérification des caractères reçus
        for (unsigned int i = 0; i < message.length(); i++) {
            if (!isDigit(message[i])) {
                return;
            }
        }

        int valeur = message.toInt();

        // Limitation à la valeur maximale du Timer1
        valeur = constrain(valeur, 0, OCR1A);

        // Mise à jour de la PWM
        OCR1B = valeur;
}


void loop() {
  
  recevoirConsignePWM();
  I = (analog.read(PIN_CAPTEUR_COURANT)/1023)*5/GAIN_COURANT;
  Omega = (analog.read(PIN_CAPTEUR_VITESSE)/1023)*5/GAIN_VITESSE;
  Serial.print(I);
  Serial.print(";");
  Serial.print(Omega);
}


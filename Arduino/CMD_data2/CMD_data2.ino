// ----------------------------------------------------- //
// LOUINEAU Ronan - GE5
// 05/11/26
// Version 1.4 : acquisition courant / vitesse ALTERNÉE (une seule conversion ADC par déclenchement)
// ----------------------------------------------------- //
//
// Instant d'échantillonnage : le convertisseur est déclenché par le BOTTOM du
// timer 1 (débordement TOV1). La MLI étant "phase et fréquence correctes",
// le BOTTOM est le milieu de l'impulsion à l'état haut : le courant y est
// échantillonné à l'écart des commutations.
//
// À chaque instant d'échantillonnage, UNE SEULE grandeur est convertie :
//   instant 0 : courant, instant 1 : vitesse, instant 2 : courant, ...
// Le temps entre deux conversions vaut N * 2 * TOP / Fclk.
// Le temps entre deux mesures d'une même grandeur vaut donc 2 * N * 2 * TOP / Fclk,
// et la vitesse k est mesurée N * 2 * TOP / Fclk APRÈS le courant k.
// ----------------------------------------------------- //


// --------------------Librairie----------------------- //

#define T_h 0.0001    // T_hash = 100, micro sec
#define TN_h 799      // TOP du timer 1 : période MLI = 2 * 799 / 16 MHz = 99,875 µs
#define Fclkio 16000000.0

// --- Assignation des broches ---
const int PIN_ALIM = A9; // PK1 : tension fixe
const int PIN_CAPTEUR_COURANT = A11; // PK2 : Capteur courant (10 V/A)
const int PIN_CAPTEUR_VITESSE = A15; // PK7 : Capteur vitesse (1 V/rad/s)

const float GAIN_COURANT = 10.0;   // 10 V/A
const float GAIN_VITESSE = 1.0;    // 1 V/rad/s

// --- Acquisition ---
#define NB_MAX 1400   // taille du tampon : 2 tableaux x 1400 x 2 octets = 5600 octets de SRAM (8 ko sur Mega)

// ADC : référence AVcc (5 V), canal ADC14 = A14 (courant) et ADC15 = A15 (vitesse)
// MUX5 (dans ADCSRB) reste à 1 pour les deux canaux
#define ADMUX_COURANT ((1 << REFS0) | 6)
#define ADMUX_VITESSE ((1 << REFS0) | 7)

// Prédiviseur ADC /32 -> horloge ADC 500 kHz, une conversion = 26 µs
// (une seule conversion par déclenchement : large marge sur les 100 µs d'une période MLI)
#define ADC_PRESCALER ((1 << ADPS2) | (1 << ADPS0))

volatile uint16_t tab_courant[NB_MAX];
volatile uint16_t tab_vitesse[NB_MAX];

volatile uint16_t idx = 0;          // nombre de mesures enregistrées
volatile uint16_t nb_ech = 0;       // nombre de mesures demandé
volatile uint16_t n_dec = 1;        // 1 mesure toutes les n_dec périodes MLI
volatile uint16_t cpt_dec = 1;
volatile uint32_t periodes = 0;     // périodes MLI écoulées pendant l'acquisition
volatile uint16_t perdus = 0;       // déclenchements arrivés pendant le traitement (mesure suspecte)
volatile uint8_t etape = 0;         // 0 : conversion du courant, 1 : conversion de la vitesse
volatile bool fini = true;

unsigned long t_debut_us = 0;
unsigned long t_fin_us = 0;


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
  OCR1B = 0;                                   // V initial OCR1A / 2

  DDRA = 0x00;
  DDRC = 0x00;

  // configuration de l'ADC (déclenchement automatique inactif tant qu'aucune acquisition n'est lancée)
  ADMUX  = ADMUX_COURANT;
  ADCSRB = (1 << MUX5) | (1 << ADTS2) | (1 << ADTS1);  // MUX5 = 1 : canaux ADC8..15 ; ADTS = 110 : débordement du timer 1
  DIDR2  = (1 << ADC14D) | (1 << ADC15D);              // coupe les buffers numériques de A14 et A15
  ADCSRA = (1 << ADEN) | ADC_PRESCALER;                // ADC activé
  ADCSRA |= (1 << ADSC);                               // conversion à blanc (la première est plus longue)
  while (ADCSRA & (1 << ADSC)) { }
}


// Fin de conversion ADC (déclenchée par le BOTTOM du timer 1).
// Une seule grandeur est convertie par déclenchement : courant, puis vitesse au
// déclenchement enregistré suivant, puis courant, etc.
// Entre deux mesures enregistrées, les conversions des périodes MLI intermédiaires
// (si n_dec > 1) sont faites sur le même canal et ignorées.
ISR(ADC_vect) {
  periodes++;
  if (--cpt_dec == 0) {
    cpt_dec = n_dec;
    if (etape == 0) {
      tab_courant[idx] = ADC;
      ADMUX = ADMUX_VITESSE;           // le prochain instant mesurera la vitesse
      etape = 1;
    } else {
      tab_vitesse[idx] = ADC;
      ADMUX = ADMUX_COURANT;           // le prochain instant mesurera le courant
      etape = 0;
      idx++;
      if (idx >= nb_ech) {
        ADCSRA &= ~((1 << ADATE) | (1 << ADIE));   // fin : plus de déclenchement, plus d'interruption
        fini = true;
      }
    }
  }
  // ADMUX est modifié AVANT l'acquittement du déclencheur (sinon on ne sait pas
  // quel canal sera converti au prochain BOTTOM)
  TIFR1 = (1 << TOV1);                 // acquitte le déclencheur, sinon pas de nouveau déclenchement
  // Un déclenchement manqué se détecte côté Python : durée mesurée par micros()
  // incohérente avec le nombre de périodes MLI comptées (variable "periodes").
}


// Lance l'acquisition, attend sa fin puis envoie les données
void acquisition(uint16_t consigne, uint16_t n, uint16_t nb) {
  n_dec = n;
  nb_ech = nb;
  cpt_dec = 1;          // la première période est enregistrée (t = 0)
  idx = 0;
  periodes = 0;
  perdus = 0;
  etape = 0;
  fini = false;

  ADMUX = ADMUX_COURANT;
  ADCSRA |= (1 << ADIF);                  // efface un éventuel drapeau ADC en attente

  noInterrupts();
  TIFR1 = (1 << TOV1);                    // le prochain BOTTOM sera le premier déclenchement
  t_debut_us = micros();
  OCR1B = consigne;                       // OCR1B est tamponné : pris en compte au prochain BOTTOM, comme le 1er déclenchement
  ADCSRA |= (1 << ADATE) | (1 << ADIE);   // déclenchement automatique + interruption
  interrupts();

  while (!fini) { }
  t_fin_us = micros();
  OCR1B = 0;                              // moteur coupé en fin d'acquisition

  // Envoi des données (le moteur est déjà arrêté, plus de contrainte de temps)
  Serial.print("DEBUT,");
  Serial.print(consigne);
  Serial.print(',');
  Serial.print(n);
  Serial.print(',');
  Serial.print(nb);
  Serial.print(',');
  Serial.println(TN_h);

  for (uint16_t k = 0; k < nb; k++) {
    Serial.print(tab_courant[k]);
    Serial.print(',');
    Serial.println(tab_vitesse[k]);
  }

  Serial.print("FIN,");
  Serial.print(perdus);
  Serial.print(',');
  Serial.print(t_fin_us - t_debut_us);
  Serial.print(',');
  Serial.println(periodes);
}


void recevoirCommande() {

    if (Serial.available() > 0) {
        char message[32];
        size_t n = Serial.readBytesUntil('\n', message, sizeof(message) - 1);
        message[n] = '\0';

        // Retire les espaces et le '\r' de fin
        while (n > 0 && (message[n - 1] == '\r' || message[n - 1] == ' ')) {
            message[--n] = '\0';
        }

        // Vérification que le message n'est pas vide
        if (n == 0) {
            return;
        }

        // Commande d'acquisition : "A,<OCR1B>,<N>,<NB>"
        if (message[0] == 'A') {
            unsigned int v, nd, nb;
            if (sscanf(message, "A,%u,%u,%u", &v, &nd, &nb) != 3
                || v > TN_h || nd < 1 || nb < 1 || nb > NB_MAX) {
                Serial.println("ERR,commande invalide");
                return;
            }
            acquisition(v, nd, nb);
            return;
        }

        // Vérification des caractères reçus
        for (unsigned int i = 0; i < n; i++) {
            if (!isDigit(message[i])) {
                return;
            }
        }

        int valeur = atoi(message);

        // Limitation à la valeur maximale du Timer1
        valeur = constrain(valeur, 0, TN_h);

        // Mise à jour de la PWM
        OCR1B = valeur;

        Serial.print("Nouveau OCR1B = ");
        Serial.println(OCR1B);
    }
}


void loop() {
  
  recevoirCommande();
  
}

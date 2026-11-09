// ----------------------------------------------------- //
// LOUINEAU Ronan - GE5
// 05/11/26
// Version 1.3 : Alim moteur MLI + communication python
//               + acquisition courant / vitesse synchronisée sur la MLI
// ----------------------------------------------------- //
//
// Commandes reçues sur le port série (terminées par '\n') :
//   "<n>"            : OCR1B = n (comportement de la version 1.2, réponse "Nouveau OCR1B = n")
//   "A,<v>,<N>,<NB>" : acquisition. Échelon OCR1B = v appliqué à t = 0,
//                      1 mesure toutes les N périodes MLI, NB mesures au total.
//
// Réponse à une acquisition (envoyée APRÈS la fin de l'acquisition) :
//   DEBUT,<OCR1B>,<N>,<NB>,<TOP>
//   <courant_brut>,<vitesse_brut>      (NB lignes, valeurs ADC 0..1023)
//   FIN,<mesures_perdues>,<duree_us>,<periodes_mli>
//
// Instant d'échantillonnage : le convertisseur est déclenché par le BOTTOM du
// timer 1 (débordement TOV1). La MLI étant "phase et fréquence correctes",
// le BOTTOM est le milieu de l'impulsion à l'état haut : le courant y est
// échantillonné à l'écart des commutations. La vitesse est mesurée juste
// après, dans la même période MLI.
// Le temps entre deux mesures vaut donc exactement N * 2 * TOP / Fclk.
// ----------------------------------------------------- //

// --------------------Librairie----------------------- //

#define T_h 0.0001    // T_hash = 100, micro sec
#define TN_h 799      // TOP du timer 1 : période MLI = 2 * 799 / 16 MHz = 99,875 µs
#define Fclkio 16000000.0

// --- Assignation des broches ---
const int PIN_ALIM = A9; // PK1 : tension fixe
const int PIN_CAPTEUR_COURANT = A14; // PK6 : Capteur courant (10 V/A)
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
// (2 conversions = environ 65 µs sur les 100 µs d'une période MLI)
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


// Fin de conversion ADC : enchaîne courant puis vitesse, tout est stocké en RAM
ISR(ADC_vect) {
  if (etape == 0) {
    // Conversion du COURANT terminée (déclenchée par le BOTTOM du timer 1)
    TIFR1 = (1 << TOV1);               // acquitte le déclencheur, sinon pas de nouveau déclenchement
    periodes++;
    if (--cpt_dec == 0) {
      cpt_dec = n_dec;
      tab_courant[idx] = ADC;
      ADMUX = ADMUX_VITESSE;
      etape = 1;
      ADCSRA |= (1 << ADSC);           // enchaîne la conversion de la VITESSE
    }
  } else {
    // Conversion de la VITESSE terminée
    tab_vitesse[idx] = ADC;
    ADMUX = ADMUX_COURANT;
    etape = 0;
    if (TIFR1 & (1 << TOV1)) {
      perdus++;                        // un BOTTOM est arrivé avant la fin du traitement
    }
    idx++;
    if (idx >= nb_ech) {
      ADCSRA &= ~((1 << ADATE) | (1 << ADIE));   // fin : plus de déclenchement, plus d'interruption
      fini = true;
    }
  }
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

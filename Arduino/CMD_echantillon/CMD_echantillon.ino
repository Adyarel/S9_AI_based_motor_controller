// Acquisition continue pour Python/dataset_generation_V2/acquisition_echantillon.py, Mega 2560.
// Timer 1 et canaux ADC14/ADC15 identiques à CMD_data.ino.
// 115200 bauds ; courant/vitesse alternés à environ 100 Hz par grandeur.
// Aucun envoi série dans l'interruption. Une saturation du tampon arrête l'essai.

#define TN_H 799
#define N_DEC 50
#define MAX_COMMANDES 64
#define MAX_DUREE_MS 60000UL
#define TAILLE_TAMPON 32
#define ADMUX_COURANT ((1 << REFS0) | 6)
#define ADMUX_VITESSE ((1 << REFS0) | 7)
#define ADC_PRESCALER ((1 << ADPS2) | (1 << ADPS0))

struct Commande {
  uint32_t periodes;
  uint16_t pwm;
};

struct Mesure {
  uint32_t tick;
  uint16_t brut;
  uint16_t pwm;
  uint8_t canal;
  uint8_t commande;
};

Commande commandes[MAX_COMMANDES];
volatile Mesure tampon[TAILLE_TAMPON];
volatile uint8_t tete = 0, queue = 0;
volatile bool actif = false;
volatile uint8_t commande_courante = 0, canal = 0;
volatile uint16_t decimation = 1, pertes = 0;
volatile uint32_t tick = 0, restantes = 0;
uint8_t attendues = 0, chargees = 0;
uint32_t duree_totale_ms = 0, envoyees = 0;
bool transmission = false;
char ligne[48];
uint8_t longueur = 0;
bool ligne_trop_longue = false;
unsigned long dernier_octet_ms = 0;

void couperMoteur() {
  ADCSRA &= ~((1 << ADATE) | (1 << ADIE));
  OCR1B = 0;
  actif = false;
}

void annulerSequence() {
  noInterrupts();
  couperMoteur();
  tete = queue = 0;
  interrupts();
  transmission = false;
  attendues = chargees = 0;
  duree_totale_ms = 0;
}

ISR(ADC_vect) {
  if (!actif) {
    TIFR1 = (1 << TOV1);
    return;
  }
  if (--decimation == 0) {
    decimation = N_DEC;
    uint8_t suivant = (tete + 1) % TAILLE_TAMPON;
    if (suivant == queue) {
      pertes++;
      couperMoteur();
    } else {
      tampon[tete].tick = tick;
      tampon[tete].brut = ADC;
      tampon[tete].pwm = commandes[commande_courante].pwm;
      tampon[tete].canal = canal;
      tampon[tete].commande = commande_courante + 1;
      tete = suivant;
      canal ^= 1;
      ADMUX = canal == 0 ? ADMUX_COURANT : ADMUX_VITESSE;
    }
  }
  tick++;
  if (actif && --restantes == 0) {
    commande_courante++;
    if (commande_courante >= attendues) {
      couperMoteur();
    } else {
      restantes = commandes[commande_courante].periodes;
      // OCR1B est tamponné : le nouveau palier commence au prochain BOTTOM.
      OCR1B = commandes[commande_courante].pwm;
    }
  }
  TIFR1 = (1 << TOV1);
}

bool entierBorne(const char *&curseur, uint32_t maximum, uint32_t &valeur) {
  if (*curseur < '0' || *curseur > '9') return false;
  valeur = 0;
  do {
    uint8_t chiffre = *curseur - '0';
    if (valeur > maximum / 10 ||
        (valeur == maximum / 10 && chiffre > maximum % 10)) return false;
    valeur = valeur * 10 + chiffre;
    curseur++;
  } while (*curseur >= '0' && *curseur <= '9');
  return true;
}

void erreurCommande() {
  annulerSequence();
  Serial.println("ERR,commande invalide");
}

void lancerSequence() {
  Serial.print("DEBUT,");
  Serial.print(TN_H);
  Serial.print(',');
  Serial.print(N_DEC);
  Serial.print(',');
  Serial.println(attendues);
  envoyees = 0;
  transmission = true;
  noInterrupts();
  tete = queue = 0;
  tick = 0;
  commande_courante = canal = 0;
  pertes = 0;
  decimation = 1;
  restantes = commandes[0].periodes;
  ADMUX = ADMUX_COURANT;
  ADCSRA |= (1 << ADIF);
  TIFR1 = (1 << TOV1);
  OCR1B = commandes[0].pwm;
  actif = true;
  ADCSRA |= (1 << ADATE) | (1 << ADIE);
  interrupts();
}

void traiterCommande(const char *message) {
  if (strcmp(message, "0") == 0) {
    annulerSequence();
    Serial.println("ARRET");
    return;
  }
  if (actif || transmission) {
    erreurCommande();
    return;
  }
  if (strcmp(message, "ID") == 0) {
    Serial.println("PRET,ECHANTILLON,1,799,50,64,60000");
    return;
  }
  if (strncmp(message, "SEQ,", 4) == 0) {
    uint32_t nombre;
    const char *curseur = message + 4;
    if (!entierBorne(curseur, MAX_COMMANDES, nombre) || nombre == 0 || *curseur != '\0') {
      erreurCommande();
      return;
    }
    annulerSequence();
    attendues = nombre;
    Serial.println("OK,SEQ");
    return;
  }
  if (strncmp(message, "C,", 2) == 0) {
    uint32_t duree, pwm;
    const char *curseur = message + 2;
    if (chargees >= attendues || !entierBorne(curseur, MAX_DUREE_MS, duree)
        || duree == 0 || *curseur++ != ',' || !entierBorne(curseur, TN_H, pwm)
        || *curseur != '\0' || duree_totale_ms + duree > MAX_DUREE_MS) {
      erreurCommande();
      return;
    }
    commandes[chargees].periodes = (duree * 16000UL + 2 * TN_H - 1) / (2 * TN_H);
    commandes[chargees].pwm = pwm;
    duree_totale_ms += duree;
    chargees++;
    Serial.print("OK,C,");
    Serial.println(chargees);
    return;
  }
  if (strcmp(message, "GO") == 0 && attendues > 0 && chargees == attendues) {
    lancerSequence();
    return;
  }
  erreurCommande();
}

void recevoirCommandes() {
  // Lecture non bloquante : une commande incomplète ne retarde pas le flux ADC.
  while (Serial.available() > 0) {
    char c = Serial.read();
    dernier_octet_ms = millis();
    if (c == '\n') {
      if (ligne_trop_longue) {
        erreurCommande();
      } else {
        ligne[longueur] = '\0';
        traiterCommande(ligne);
      }
      longueur = 0;
      ligne_trop_longue = false;
    } else if (c != '\r') {
      if (longueur < sizeof(ligne) - 1) ligne[longueur++] = c;
      else ligne_trop_longue = true;
    }
  }
  if ((longueur || ligne_trop_longue) && millis() - dernier_octet_ms > 1000UL) {
    longueur = 0;
    ligne_trop_longue = false;
    erreurCommande();
  }
}

void transmettreMesure() {
  if (!transmission) return;
  if (queue != tete) {
    // Le producteur ISR ne réécrit pas cette case avant l'avancement de queue.
    Mesure mesure;
    mesure.tick = tampon[queue].tick;
    mesure.brut = tampon[queue].brut;
    mesure.pwm = tampon[queue].pwm;
    mesure.canal = tampon[queue].canal;
    mesure.commande = tampon[queue].commande;
    queue = (queue + 1) % TAILLE_TAMPON;
    Serial.print("M,");
    Serial.print(mesure.tick);
    Serial.print(',');
    Serial.print(mesure.canal);
    Serial.print(',');
    Serial.print(mesure.brut);
    Serial.print(',');
    Serial.print(mesure.commande);
    Serial.print(',');
    Serial.println(mesure.pwm);
    envoyees++;
  }
  if (!actif && queue == tete) {
    Serial.print("FIN,");
    Serial.print(envoyees);
    Serial.print(',');
    Serial.println(pertes);
    transmission = false;
    attendues = chargees = 0;
    duree_totale_ms = 0;
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(A9, OUTPUT);
  digitalWrite(A9, LOW);
  delay(500);
  digitalWrite(A9, HIGH);
  DDRB |= (1 << 6);  // PB6 = OC1B, sortie MLI identique au montage existant
  TCCR1A = (1 << COM1B1) | (1 << WGM10);
  TCCR1B = (1 << ICNC1) | (1 << WGM13) | (1 << CS10);
  OCR1A = TN_H;
  OCR1B = 0;
  ADMUX = ADMUX_COURANT;
  ADCSRB = (1 << MUX5) | (1 << ADTS2) | (1 << ADTS1);
  DIDR2 = (1 << ADC14D) | (1 << ADC15D);
  ADCSRA = (1 << ADEN) | ADC_PRESCALER;
  ADCSRA |= (1 << ADSC);
  while (ADCSRA & (1 << ADSC)) { }
}

void loop() {
  recevoirCommandes();
  transmettreMesure();
}

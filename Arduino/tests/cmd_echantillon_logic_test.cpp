// Tests PC : registres/ADC/liaison simulés, sans émulation des cycles AVR.
#include <cstdint>
#include <cstring>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

constexpr int A9 = 63, OUTPUT = 1, LOW = 0, HIGH = 1;
constexpr int REFS0 = 6, ADPS2 = 2, ADPS0 = 0, COM1B1 = 5;
constexpr int WGM10 = 0, ICNC1 = 7, WGM13 = 4, CS10 = 0;
constexpr int MUX5 = 3, ADTS2 = 2, ADTS1 = 1, ADC14D = 6, ADC15D = 7;
constexpr int ADEN = 7, ADSC = 6, ADATE = 5, ADIF = 4, ADIE = 3, TOV1 = 0;
std::uint8_t DDRB, TCCR1A, TCCR1B, ADMUX, ADCSRB, DIDR2, TIFR1;
std::uint16_t OCR1A, OCR1B, ADC;
struct AdcControl {
    std::uint8_t value = 0;
    operator std::uint8_t() const { return value; }
    AdcControl& operator=(int n) { value = n; return *this; }
    AdcControl& operator|=(int n) {
        value |= n;
        if ((value & (1 << ADSC)) && !(value & (1 << ADATE))) value &= ~(1 << ADSC);
        return *this;
    }
    AdcControl& operator&=(int n) { value &= n; return *this; }
} ADCSRA;
struct MockSerial {
    std::string input, output;
    unsigned long baud = 0;
    void begin(unsigned long n) { baud = n; }
    int available() const { return static_cast<int>(input.size()); }
    int read() { unsigned char c = input.front(); input.erase(0, 1); return c; }
    void print(std::uint8_t n) { output += std::to_string(n); }
    template<class T> void print(T n) { std::ostringstream s; s << n; output += s.str(); }
    template<class T> void println(T n) { print(n); output += '\n'; }
} Serial;
unsigned long now_ms = 0;
void pinMode(int, int) {}
void digitalWrite(int, int) {}
void delay(unsigned long ms) { now_ms += ms; }
unsigned long millis() { return now_ms; }
void noInterrupts() {}
void interrupts() {}
#define ISR(vector) void vector()

#include "../CMD_echantillon/CMD_echantillon.ino"

void require(bool condition, const std::string& detail) {
    if (!condition) throw std::runtime_error(detail);
}
void reset() {
    annulerSequence();
    Serial.input.clear(); Serial.output.clear();
    longueur = 0; ligne_trop_longue = false; now_ms = 0;
    ADC = 0; DDRB = 0; ADCSRA = 0;
}
void send(const std::string& command) {
    Serial.input += command;
    recevoirCommandes();
}
void prepare() {
    send("SEQ,2\nC,20,200\nC,30,599\n");
    require(Serial.output == "OK,SEQ\nOK,C,1\nOK,C,2\n", "wrong upload acknowledgement");
    Serial.output.clear();
    send("GO\n");
}
void step(bool drain = true) {
    require(actif, "step on inactive acquisition");
    ADC = canal == 0 ? 123 : 456;
    ADC_vect();
    if (drain) transmettreMesure();
}
void finish(bool drain = true) {
    unsigned guard = 0;
    while (actif) {
        require(++guard < 1000000, "sequence did not finish");
        step(drain);
    }
    while (transmission) transmettreMesure();
}
void check_sequence() {
    reset(); prepare();
    require(OCR1B == 200 && actif, "wrong initial PWM");
    std::vector<unsigned> pwm;
    while (actif) { pwm.push_back(OCR1B); step(); }
    while (transmission) transmettreMesure();
    require(pwm.size() == 502, "wrong total duration");
    for (unsigned i = 0; i < pwm.size(); ++i)
        require(pwm[i] == (i < 201 ? 200U : 599U), "interruption between PWM steps");
    require(OCR1B == 0 && !(ADCSRA & ((1 << ADATE) | (1 << ADIE))), "not stopped at end");
    std::istringstream output(Serial.output);
    std::string line;
    std::getline(output, line);
    require(line == "DEBUT,799,50,2", "wrong header");
    for (unsigned i = 0; i < 11; ++i) {
        std::getline(output, line);
        std::string expected = "M," + std::to_string(i*50) + "," + std::to_string(i%2)
            + "," + std::to_string(i%2 == 0 ? 123 : 456)
            + (i < 5 ? ",1,200" : ",2,599");
        require(line == expected, "wrong streamed sample: " + line);
    }
    std::getline(output, line);
    require(line == "FIN,11,0", "wrong footer");
    require(!std::getline(output, line), "unexpected extra output");
}

// Adaptateur de simulation : les commandes pilotent le vrai sketch inclus.
// Les ticks sont accélérés, les ADC restent synthétiques (123 et 456).
int simulate_serial() {
    reset(); setup(); Serial.output.clear();
    std::string request;
    while (std::getline(std::cin, request)) {
        if (request.rfind("SEND ", 0) == 0) {
            send(request.substr(5) + "\n");
        } else if (request == "READ") {
            while (Serial.output.empty() && (actif || transmission)) {
                if (actif) step(false);
                transmettreMesure();
            }
        } else if (request.rfind("STALL ", 0) == 0) {
            unsigned count = static_cast<unsigned>(std::stoul(request.substr(6)));
            while (count-- && actif) step(false);
        } else {
            return 2;
        }
        std::cout << Serial.output.size() << ',' << OCR1B << ',' << actif << ','
                  << tick << '\n' << Serial.output << std::flush;
        Serial.output.clear();
    }
    return 0;
}

int main(int argc, char** argv) {
    if (argc == 2 && std::string(argv[1]) == "--simulate-serial") return simulate_serial();
    if (argc == 2 && std::string(argv[1]) == "--transcript") {
        reset(); prepare(); finish(); std::cout << Serial.output; return 0;
    }
    unsigned passed = 0, failed = 0;
    auto test = [&](const std::string& name, const auto& fn) {
        try { fn(); ++passed; std::cout << "PASS " << name << '\n'; }
        catch (const std::exception& e) { ++failed; std::cout << "FAIL " << name << ": " << e.what() << '\n'; }
    };
    test("setup starts stopped and configures PWM/ADC", [] {
        reset(); setup();
        require(Serial.baud == 115200 && OCR1A == 799 && OCR1B == 0, "wrong setup");
        require(ADMUX == ADMUX_COURANT && !(ADCSRA & (1 << ADATE)), "wrong ADC setup");
    });
    test("identification", [] {
        reset(); send("ID\r\n");
        require(Serial.output == "PRET,ECHANTILLON,1,799,50,64,60000\n", "wrong identification");
    });
    test("PWM sequence and streamed values", check_sequence);
    test("successive sequences", [] { check_sequence(); check_sequence(); });
    test("stop interrupts acquisition and discards pending samples", [] {
        reset(); prepare(); step(false); send("0\n");
        require(!actif && !transmission && OCR1B == 0 && tete == queue, "stop failed");
        require(Serial.output.find("ARRET\n") != std::string::npos, "missing stop acknowledgement");
    });
    test("ring overflow stops PWM and reports a lost sample", [] {
        reset(); send("SEQ,1\nC,1000,400\nGO\n"); finish(false);
        require(!actif && OCR1B == 0 && pertes == 1, "overflow not stopped");
        require(Serial.output.find("FIN,31,1\n") != std::string::npos, "overflow not reported");
    });
    test("one millisecond and zero PWM", [] {
        reset(); send("SEQ,1\nC,1,0\nGO\n"); finish();
        require(tick == 11 && OCR1B == 0, "wrong short duration");
        require(Serial.output.find("FIN,1,0\n") != std::string::npos, "wrong short record count");
    });
    test("maximum sequence duration", [] {
        reset(); send("SEQ,1\nC,60000,799\nGO\n"); finish();
        require(tick == 600751 && OCR1B == 0, "wrong maximum duration");
        require(Serial.output.find("FIN,12016,0\n") != std::string::npos, "wrong max sample count");
    });
    test("64 commands", [] {
        reset(); send("SEQ,64\n");
        for (unsigned i = 0; i < 64; ++i) send("C,1," + std::to_string(i) + "\n");
        send("GO\n"); finish();
        require(tick == 64*11 && OCR1B == 0 && pertes == 0, "wrong 64-command sequence");
    });
    test("oversized and unterminated lines", [] {
        reset(); send(std::string(100, '9') + "\n");
        require(Serial.output == "ERR,commande invalide\n", "oversized line accepted");
        Serial.output.clear(); send("C,20"); now_ms += 1001; recevoirCommandes();
        require(Serial.output == "ERR,commande invalide\n" && longueur == 0, "partial line retained");
    });
    test("command during acquisition aborts", [] {
        reset(); prepare(); send("GO\n");
        require(!actif && OCR1B == 0 && !transmission, "unexpected GO did not abort");
    });
    for (const std::string command : {
        "SEQ,0", "SEQ,65", "SEQ,-1", "SEQ,1x", "SEQ,99999999999999999999999",
        "GO", "C,1,1", "SEQ,1\nGO", "SEQ,1\nC,0,1", "SEQ,1\nC,60001,1",
        "SEQ,1\nC,1,800", "SEQ,1\nC,-1,200", "SEQ,1\nC,1,200x",
        "SEQ,1\nC,1,200,1", "SEQ,1\nC,1", "SEQ,1\nC,,1", "SEQ,1\nC,1,",
        "SEQ,2\nC,30001,100\nC,30000,100", "SEQ,1\nC,1,1\nC,1,1"
    }) {
        test("reject malformed sequence " + command, [command] {
            reset(); send(command + "\n");
            require(!actif && OCR1B == 0 && attendues == 0, "invalid sequence retained");
            require(Serial.output.find("ERR,commande invalide\n") != std::string::npos, "no error reported");
        });
    }
    std::cout << "RESULT " << passed << " passed, " << failed << " failed\n";
    return failed ? 1 : 0;
}

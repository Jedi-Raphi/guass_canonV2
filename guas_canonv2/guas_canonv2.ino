#include "hardware/pio.h"
#include "structure.h"
#include "pio_code.h"

#define DEBUG 0

int Green_pin = 29;  // pin de la led verte

extern pio_config Coil_sm;
extern pio_config Timer_sm;



data_time_s data_time[nb_coil]{};

int curent_coil = 0;

void setup() {
  Serial.begin(115200);                      // initialisation du moniteur serie
  delay(2000);                               // attendre qu'il demare
#if DEBUG                                    //
  Serial.println("initialisation des pio");  //
#endif                                       //
  init_pio();                                // initialisation des pio et SM voir dans pio_handler.ino
#if DEBUG                                    //
  Serial.println("pio initialisés");         //
#endif                                       //
  gpio_init(Green_pin);                      // initialisation du pin pour la led verte
  gpio_set_dir(Green_pin, true);             // comme sortie
  gpio_put(Green_pin, HIGH);                 // allumer led verte


  Serial.print("start Offset");
  Serial.print("\t");

  for (int i = 0; i < nb_coil; i++) {

    Serial.print("start pulse of coil ");
    Serial.print(i);
    Serial.print("\t");
    Serial.print("end pulse");
    Serial.print(i);
    Serial.print("\t");
    Serial.print("length pulse");
    Serial.print(i);
    Serial.print("\t");
  }
  Serial.println("");
}




void loop() {
  gpio_put(Green_pin, HIGH);  // allumer led verte
  restart_timer();

  for (int i = 0; i < nb_coil; i++) {
#if DEBUG
    Serial.print("init bobine : ");
    Serial.println(i);
#endif

    init_coil(i);
    while (!pio_interrupt_get(Coil_sm.pio, 0)) {
    }
    shutdown_coil(i);
    gpio_put(Green_pin, LOW);
    data_time[i].l_pulse = (uint64_t)(0xFFFFFFFF - pio_sm_get(Coil_sm.pio, Coil_sm.sm))* 20ULL;
#if DEBUG
    Serial.println(data_time[i].l_pulse);
#endif

#if DEBUG
    Serial.println("detected");
#endif
    if (pio_interrupt_get(Timer_sm.pio, 2) && pio_interrupt_get(Timer_sm.pio, 3)) {
      data_time[i].start_pulse = (uint64_t)(0xFFFFFFFF - pio_sm_get(Timer_sm.pio, Timer_sm.sm))* 20ULL;
      data_time[i].end_pulse = (uint64_t)(0xFFFFFFFF - pio_sm_get(Timer_sm.pio, Timer_sm.sm))* 20ULL;
#if DEBUG
      Serial.println(data_time[i].start_pulse);
      Serial.println(data_time[i].end_pulse);
#endif

      pio_interrupt_clear(Timer_sm.pio, 2);
      pio_interrupt_clear(Timer_sm.pio, 3);
    }



    pio_interrupt_clear(Coil_sm.pio, 0);
  }
  uint64_t zero = data_time[0].start_pulse;
  Serial.print(zero);
  Serial.print("\t");
  for (int i = 0; i < nb_coil; i++) {
    Serial.print(data_time[i].start_pulse - zero);
    Serial.print("\t");
    Serial.print(data_time[i].end_pulse - zero);
    Serial.print("\t");
    Serial.print(data_time[i].l_pulse);
    Serial.print("\t");
  }
  Serial.println("");
}

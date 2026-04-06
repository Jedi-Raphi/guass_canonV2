
pio_config Coil_sm = {};  // initialisation de la config de la System Machine qui gere les bobines
pio_config Timer_sm = {
  // initialisation de la config de la System Machine qui gere le timer
  .pio = pio1  // sur le 2e pio (par manque de place sur le 1er pio)
};



int flag_pio = 10;  // pin qui sert de drapeau entre les deux SM (coil_handler et timer)



void init_pio() {
  //initialisation de la SM gerant les bobines
  Coil_sm.offset = pio_add_program(Coil_sm.pio, &Coil_handler_program);    // on charge le programe dans pio
  Coil_sm.sm = pio_claim_unused_sm(Coil_sm.pio, true);                     // on aloue un SM pour gere les bobines
  Coil_sm.conf = Coil_handler_program_get_default_config(Coil_sm.offset);  // on lui cree une config


  //initialisation de la SM gerant le timer
  Timer_sm.offset = pio_add_program(Timer_sm.pio, &Timer_program);    // on charge le programe dans pio
  Timer_sm.sm = pio_claim_unused_sm(Timer_sm.pio, true);              // on aloue un SM pour gère le timer
  Timer_sm.conf = Timer_program_get_default_config(Timer_sm.offset);  // on lui cree une config



  // on initialise le drapeau inter SM
  pio_gpio_init(Coil_sm.pio, flag_pio);                                        // on donne le controle de la pin a la SM qui gere les bobines
  sm_config_set_sideset_pins(&Coil_sm.conf, flag_pio);                         // on lui donne comme side_set
  pio_sm_set_consecutive_pindirs(Coil_sm.pio, Coil_sm.sm, flag_pio, 1, true);  // on s'assure qu'elle est bien une sortie
  sm_config_set_in_pins(&Timer_sm.conf, flag_pio);                             // on la definie comme la nouvelle In_pin dans la SM du timer
  sm_config_set_jmp_pin(&Timer_sm.conf, flag_pio);                             // on la definie comme la nouvelle jmp_pin dans la SM du timer

  pio_sm_init(Coil_sm.pio, Coil_sm.sm, Coil_sm.offset, &Coil_sm.conf);      //applique la conf
  pio_sm_init(Timer_sm.pio, Timer_sm.sm, Timer_sm.offset, &Timer_sm.conf);  //applique la conf
}



void init_coil(uint coil_to_init) {
  pio_sm_set_enabled(Coil_sm.pio, Coil_sm.sm, false);  //mettre la SM en pause pour eviter tout probleme


  // initialisation du pin du mosfet / led dans la SM
  pio_gpio_init(Coil_sm.pio, Coil_parameter[coil_to_init].mosfetpin);
  sm_config_set_set_pins(&Coil_sm.conf, Coil_parameter[coil_to_init].mosfetpin, 1);
  pio_sm_set_consecutive_pindirs(Coil_sm.pio, Coil_sm.sm, Coil_parameter[coil_to_init].mosfetpin, 1, true);
  



    // initialisation du pin du capteur optique
    pio_gpio_init(Coil_sm.pio, Coil_parameter[coil_to_init].photopin);                                       // on donne le pin a la SM
  pio_sm_set_consecutive_pindirs(Coil_sm.pio, Coil_sm.sm, Coil_parameter[coil_to_init].photopin, 1, false);  // on s'assure qu'elle est bien une sortie
                                                                                                             // gpio_disable_pulls(Coil_parameter[coil_to_init].photopin);
  gpio_set_pulls(Coil_parameter[coil_to_init].photopin, false, false);                                       // on desactive les resistance de pull Up/down

  sm_config_set_in_pins(&Coil_sm.conf, Coil_parameter[coil_to_init].photopin);  // on la definie comme la nouvelle In_pin dans la SM
  // redemarage de la SM

  pio_sm_init(Coil_sm.pio, Coil_sm.sm, Coil_sm.offset, &Coil_sm.conf);  // aplique la nouvelle config et  vide l'isr et L'osr comme un pio_sm_restart
  pio_sm_clkdiv_restart(Coil_sm.pio, Coil_sm.sm);                       // resynchronise l'horloge interne du pio
  pio_sm_clear_fifos(Coil_sm.pio, Coil_sm.sm);                          // vide le fifo
  pio_sm_set_enabled(Coil_sm.pio, Coil_sm.sm, true);                    //demare la SM
}

void shutdown_coil(uint coil_to_shutdown) {
  gpio_init(coil_to_shutdown);
  gpio_set_dir(coil_to_shutdown, true);
  gpio_put(coil_to_shutdown, 0);
}

void restart_timer() {
  pio_sm_set_enabled(Timer_sm.pio, Timer_sm.sm, false);  //mettre la SM en pause pour eviter tout probleme
  pio_sm_init(Timer_sm.pio, Timer_sm.sm, Timer_sm.offset, &Timer_sm.conf);
  pio_sm_clkdiv_restart(Timer_sm.pio, Timer_sm.sm);     // resynchronise l'horloge interne du pio
  pio_sm_clear_fifos(Timer_sm.pio, Timer_sm.sm);        // vide le fifo
  pio_sm_set_enabled(Timer_sm.pio, Timer_sm.sm, true);  //demare la SM
}

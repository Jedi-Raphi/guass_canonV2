struct pio_config {  // declaration de la structure contenant les parametres des 2 codes pio
  PIO pio = pio0;
  uint sm;
  uint offset;
  pio_sm_config conf;
};

struct coil_handler_struc {  // declaration de la structure contenant les parametres et pins de chaque bobine / capteur
  uint photopin;
  uint mosfetpin;  // ou juste led d'affichage
  uint timebeforetrig = 0;
  uint maxtime = 10 * 1000 * 1000;
};

struct data_time_s {
  uint64_t l_pulse;
  uint64_t start_pulse;
  uint64_t end_pulse;
};




coil_handler_struc Coil_parameter[]{
  {
    .photopin = 3,  // 1e bobine
    .mosfetpin = 26,
  },
  {
    .photopin = 2,  // 2e bobine
    .mosfetpin = 27,
  },
  {
    .photopin = 1,  // 3e bobine
    .mosfetpin = 7,
  },
  {
    .photopin = 0,  // capteur de sortie
    .mosfetpin = 8,
  }
};

constexpr int nb_coil = sizeof(Coil_parameter) / sizeof(Coil_parameter[0]);
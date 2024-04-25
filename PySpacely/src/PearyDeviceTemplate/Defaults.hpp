#ifndef DEVICE_((devname))_DEFAULTS_H
#define DEVICE_((devname))_DEFAULTS_H

#include "utils/dictionary.hpp"

namespace caribou {

  // define voltages


  // Spacely-Caribou Address Space
  const intptr_t DEMO_BASE_ADDRESS = 0x400000000;

  const size_t DEMO_MEM_SIZE = 0x30000;


  
  const memory_map FPGA_MEM{DEMO_BASE_ADDRESS, DEMO_MEM_SIZE, PROT_READ | PROT_WRITE};



  ((mem_map))

#endif /* DEVICE_((devname))_DEFAULTS_H */

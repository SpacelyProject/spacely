/**
 * Caribou C++ Device for ((devname))
 */

#include "((devname))Device.hpp"
#include "utils/log.hpp"

using namespace caribou;

((devname))Device::((devname))Device(const caribou::Configuration config)
    : CaribouDevice(config, iface_mem::configuration_type(MEM_PATH, FPGA_MEM)) {

  
  // Set up periphery
  // (When we have a CaR Board)
  //_periphery.add("VDDA", carboard::PWR_OUT_1);

   // Add memory pages to the dictionary:
  _memory.add(FPGA_REGS);

}

void ((devname))Device::powerUp() {
  LOG(INFO) << "Powering up";
  return;
}

void ((devname))Device::powerDown() {
  LOG(INFO) << "Powering down";
  return;
}


void ((devname))Device::daqStart() {
  LOG(INFO) << "DAQ Starting";
  return;
}


void ((devname))Device::daqStop() {
  LOG(INFO) << "DAQ Stopping";
  return;
}

//Need to provide a definition for the destructor, or it will throw an error.
((devname))Device::~((devname))Device() {
  LOG(INFO) << "Shutdown, delete device.";
  powerOff();
}

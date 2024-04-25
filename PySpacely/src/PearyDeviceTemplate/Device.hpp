/**
 * Header file for the ((devname)) C++ Caribou Device
 */

#ifndef DEVICE_((devname))_H
#define DEVICE_((devname))_H

#include "device/CaribouDevice.hpp"
#include "hardware_abstraction/carboard/Carboard.hpp"

#include "((devname))Defaults.hpp"

#include <fstream>

namespace caribou {

  /** SParkDream Device class definition
   */
  class ((devname))Device : public CaribouDevice<carboard::Carboard, iface_mem> {

  public:
    ((devname))Device(const caribou::Configuration config);
    ~((devname))Device();

    void daqStart() override;
    void daqStop() override;

    void powerUp() override;
    void powerDown() override;

  };


} // namespace caribou

#endif /* DEVICE_((devname))_H */

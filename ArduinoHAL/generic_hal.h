// * * * GENERIC HARDWARE ABSTRACTION LAYER (HAL) * * *
// Adam Quinn - aquinn@fnal.gov
//
// Usage Notes:
// 1. This HAL includes optional functions with GPIO register manipulation instructions specifically
//    for the Arduino Portenta. If you want to use these functions, #define PORTENTA, and also
//    include GPI_user.cpp and GPIO_user.h


//This function is from the AVR util/delay_basic.h library.
// void _delay_loop_1(uint8_t __count)
// {
// 	__asm__ volatile (
// 		"1: dec %0" "\n\t"
// 		"brne 1b"
// 		: "=r" (__count)
// 		: "0" (__count)
// 	);
// }

/**
 * get_user_string - Gets a string from the user over Serial, trims it, and returns it.
 *  ARGUMENTS:
 *      u - Preallocated string to store the user's response. 
 * 
 * Note that "String&" passes the string u by reference. See this thread for details:
 * https://forum.arduino.cc/t/string-arguments-to-functions-string-msg-or-string-msg/629828/6
 */
void get_user_string(String& u) {
  //Clear any serial input that comes before "?"
  while (Serial.available()) Serial.read();
  Serial.print("?");

  while (!Serial.available())
    ;  //Wait for serial

  //Set Serial timeout to 10 ms if it is not already.
  //This allows us to definitely get the user's whole string, but
  //without an appreciable delay to the user. (Note that 
  //Serial.readString() will never exit early, even with \n).
  Serial.setTimeout(10); 

  //Get the user's input as a string.
  u= Serial.readString();

  //Trim space/newline characters.
  u.trim();

}

/**
 * serial_write - Writes data to an ASIC serial input.
 * ARGUMENTS:
 *    data_pin  - pin # to send data on
 *    clock_pin - pin # to send clock on
 *    data      - array containing the data to be sent.
 *    num_bits  - length of data
 *    frequency - serial clock frequency (Hz). Valid range 100 Hz ~ 5 kHz
 */
void serial_write(byte data_pin, byte clock_pin, char data[], int num_bits, long frequency) {
  long half_period_us = 1000000L / (2 * frequency);

#ifdef DEBUG
  Serial.print("Writing Data: ");
#endif

  for (int i = 0; i < num_bits; i++) {
    //Send the next data bit.
    digitalWrite(clock_pin, LOW);

#ifdef DEBUG
    Serial.print((int)data[i]);
#endif

    digitalWrite(data_pin, data[i]);

    delayMicroseconds(half_period_us);

    //Clock it in.
    digitalWrite(clock_pin, HIGH);

    delayMicroseconds(half_period_us);
  }

#ifdef DEBUG
  Serial.println();
#endif
}

#ifdef PORTENTA
/*
 * Serial write using PC6 for SCLK and PC7 for DATA
 */
void serial_write_portenta_C6_C7(char data[], int num_bits, long frequency) {
  long half_period_us = 1000000L / (2 * frequency);


  for (int i = 0; i < num_bits; i++) {
    HAL_GPIO_WritePin(GPIOC, GPIO_PIN_6, GPIO_PIN_RESET);

    if ((int)data[i])
      HAL_GPIO_WritePin(GPIOC, GPIO_PIN_7, GPIO_PIN_SET);
    else
      HAL_GPIO_WritePin(GPIOC, GPIO_PIN_7, GPIO_PIN_RESET);

    delayMicroseconds(half_period_us);

    HAL_GPIO_WritePin(GPIOC, GPIO_PIN_6, GPIO_PIN_SET);

    delayMicroseconds(half_period_us);
  }
}
#endif


/**
 * serial_read_arduino_delay - Reads data from an ASIC serial output.
 * ARGUMENTS:
 *    data_pin  - pin # to send data on
 *    clock_pin - pin # to send clock on
 *    data      - array where the data should be stored.
 *    num_bits  - length of data to read
 *    frequency - serial clock frequency (Hz). Valid range 100 Hz ~ 100 kHz
 */
void serial_read_arduino_delay(byte data_pin, byte clock_pin, char* data, int num_bits, long frequency) {
  long half_period_us = 1000000L / (2 * frequency);

  for (int i = 0; i < num_bits; i++) {
    //Send the next data bit.
    digitalWrite(clock_pin, LOW);
    data[i] = digitalRead(data_pin);

    //With delays commented out, the fastest acheivable speed is ~ 57 kHz.
    delayMicroseconds(half_period_us);


    //Clock it in.
    digitalWrite(clock_pin, HIGH);

    delayMicroseconds(half_period_us);
  }
}

/**
 * serial_read_arduino_max - Reads data from an ASIC serial output at the maximum speed acheivable by 
							 using the Arduino native digitalWrite and digitalRead commands. 
 * ARGUMENTS:
 *    data_pin  - pin # to send data on
 *    clock_pin - pin # to send clock on
 *    data      - array where the data should be stored.
 *    num_bits  - length of data to read
 */
void serial_read_arduino_max(byte data_pin, byte clock_pin, char* data, int num_bits) {

  for (int i = 0; i < num_bits; i++) {
    //Send the next data bit.
    digitalWrite(clock_pin, LOW);
    data[i] = digitalRead(data_pin);

    //Clock it in.
    digitalWrite(clock_pin, HIGH);
  }
}

#ifdef PORTENTA
/**
 * serial_read_portenta_max - Reads data from an ASIC serial output at the maximum speed acheivable by 
							  port manipulation on the portenta.
							  Using PC6 for SCLK and PG7 for DATA
 * ARGUMENTS:
 *    data_pin  - pin # to send data on
 *    clock_pin - pin # to send clock on
 *    data      - array where the data should be stored.
 *    num_bits  - length of data to read
 */
void serial_read_portenta_C6_G7_max(char* data, int num_bits) {

  for (int i = 0; i < num_bits; i++) {
    //Send the next data bit.
    HAL_GPIO_WritePin(GPIOC, GPIO_PIN_6, GPIO_PIN_RESET);

    //delayMicroseconds(1);

    data[i] = HAL_GPIO_ReadPin(GPIOG, GPIO_PIN_7);

    //delayMicroseconds(1);
    //Clock it in.
    HAL_GPIO_WritePin(GPIOC, GPIO_PIN_6, GPIO_PIN_SET);
  }
  //Make sure we end with the clock low.
  HAL_GPIO_WritePin(GPIOC, GPIO_PIN_6, GPIO_PIN_RESET);
}
#endif

/**
 * clock_pulse_arduino - sends a {microseconds}-long pulse of pulse_pin, with a rising clock edge in the middle.
 * ARGUMENTS:
 *    pulse_pin - pin # to pulse
 *    clock_pin - pin # to send clock on.
 *    microseconds - pulse width in microseconds
 */
void clock_pulse_arduino(byte pulse_pin, byte clock_pin, int microseconds) {
  digitalWrite(clock_pin, LOW);
  digitalWrite(pulse_pin, HIGH);

  delayMicroseconds(microseconds / 2);

  digitalWrite(clock_pin, HIGH);

  delayMicroseconds(microseconds / 2);

  digitalWrite(clock_pin, LOW);
  digitalWrite(pulse_pin, LOW);
}

#ifdef PORTENTA
/**
 * clock_pulse_portenta_C6 - Writes a pulse on pulse_pin, and clocks
 *          Portenta GPIO pin C6 while pulse_pin is high. 
 *
 */
void clock_pulse_portenta_C6(byte pulse_pin, int microseconds) {
  HAL_GPIO_WritePin(GPIOC, GPIO_PIN_6, GPIO_PIN_RESET);
  digitalWrite(pulse_pin, HIGH);

  delayMicroseconds(microseconds / 2);

  HAL_GPIO_WritePin(GPIOC, GPIO_PIN_6, GPIO_PIN_SET);

  delayMicroseconds(microseconds / 2);

  HAL_GPIO_WritePin(GPIOC, GPIO_PIN_6, GPIO_PIN_RESET);
  digitalWrite(pulse_pin, LOW);
}
#endif

/**
 * print_data - Prints out the contents of a data array to Serial.
 * ARGUMENTS:
 *    data_array - array containing the data
 *    len        - length of data_array
 */
void print_data(char* data_array, int len) {
  for (int k = 0; k < len; k++) {
    Serial.print((int)data_array[k]);
  }
}

void print_data_big_endian(char* data_array, int len) {
  for (int k = len - 1; k >= 0; k--) {
    Serial.print((int)data_array[k]);
  }
}


int bin_array_to_dec(char* data_array, int len) {
  int decimal_value = 0;

  for (int i = 0; i < len; i++) {
    //decimal_value = decimal_value + (int)(data_array[i] * (1 << (len - i - 1)));
    if (data_array[i]) {
      decimal_value = decimal_value + (1 << (len - i - 1));
    }
    //DEBUG:
    //Serial.println("~~~");
    //Serial.println((int)data_array[i]);
    //Serial.println(decimal_value);
  }

  return decimal_value;
}

int bin_array_to_dec_big_endian(char* data_array, int len) {
  int decimal_value = 0;

  for (int i = 0; i < len; i++) {
    //decimal_value = decimal_value + (int)(data_array[i] * (1 << (len - i - 1)));
    if (data_array[i]) {
      decimal_value = decimal_value + (1 << (i));
    }
    //DEBUG:
    //Serial.println("~~~");
    //Serial.println((int)data_array[i]);
    //Serial.println(decimal_value);
  }

  return decimal_value;
}

void detailed_print(char* data_array) {

  int qcoarse = bin_array_to_dec(&data_array[0], 10);
  int qfine = bin_array_to_dec(&data_array[10], 7);


  Serial.print("Qcoarse: ");
  Serial.print(qcoarse);
  Serial.print(" Qfine: ");
  Serial.print(qfine);
  Serial.print(" (Config bits: ");
  print_data(&data_array[17], 8);
  Serial.print(") ");

  //DEBUG:
  Serial.print("Raw Data: ");
  print_data(data_array, 25);

  Serial.println();
}

void streaming_print(char* data_array) {
  int qcoarse = bin_array_to_dec(&data_array[0], 10);
  int qfine = bin_array_to_dec(&data_array[10], 7);



  Serial.println(String(qcoarse) + "," + String(qfine));
}



void wait_on_falling_edge(byte pin) {

  unsigned long start_time = millis();

  while (digitalRead(pin) == 0) {
    //delayMicroseconds(100);
    if (millis() > (start_time + 10)) { break; }
  }

  while (digitalRead(pin) == 1) {
    //delayMicroseconds(100);
    if (millis() > (start_time + 10)) { break; }
  }

  if (millis() > (start_time + 10)) {
    Serial.println("ERR: Timeout waiting for falling edge!");
  }
}

void wait_on_rising_edge_timeout(byte pin) {

  unsigned long start_time = millis();

  while (digitalRead(pin) == 1) {
    //delayMicroseconds(100);
    if (millis() > (start_time + 10)) { break; }
  }

  while (digitalRead(pin) == 0) {
    //delayMicroseconds(100);
    if (millis() > (start_time + 10)) { break; }
  }

  if (millis() > (start_time + 10)) {
    Serial.println("ERR: Timeout waiting for falling edge!");
  }
}


void wait_on_rising_edge(byte pin) {

  byte value = 1;
  byte lastvalue = 1;

  while (true) {
    value = digitalRead(pin);
    if (value > lastvalue) break;
    lastvalue = value;
  }
}


void await_reset() {
  byte iter = 0;

  while (true) {
    //Alternate printing "*" or "."
    if (iter % 2) Serial.print(".");
    else Serial.print("*");
    iter = iter + 1;
    if (iter >= 60) {
      Serial.println("");
      iter = 0;
    }

    //Delay 1s per iteration.
    delay(1000);

    //If you get anything on the Serial, read it and then reset.
    if (Serial.available()) {
      while (Serial.available()) Serial.read();
      return;
    }
  }
}
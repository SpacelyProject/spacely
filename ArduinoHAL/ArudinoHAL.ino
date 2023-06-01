// * * * SPROCKET_HAL_Test * * *
//
// This software allows testing the SPROCKET1 test pixel,
// including performing the role of the SAR logic.

String DOCSTRING = "This Arduino is running SPROCKET_HAL_Test v0.10SLOW, updated 5/19/2023. Macros: ";

//makeinclude GPIO_user.cpp DO NOT MODIFY THIS LINE
#include "includes/GPIO_user.h"
#include "includes/generic_hal.h"

#define GPIO_NUMBER (16U)

//Variables for CDAC emulator.
float CL;
float CR;
float CompInp;
char data_array[10] = { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 };
long numConversions;

uint16_t data_buffer[100];
bool user_echo = 1;

//User input
String u;


//#define EMULATOR 1
//#define UNO 1
#define PORTENTA 1


// *** CDAC CONTROL MACROS ***
//Note that EMULATOR takes precedence over ARDUINO/PORTENTA if asserted.
#if defined(EMULATOR)
#define assert_qequal() \
  CL = (CL + CR) / 2; \
  CR = CL;
#define deassert_qequal() ;
#define assert_dacclr() CL = 0;
#define deassert_dacclr() ;
#define assert_caphi() CR = 1;
#define deassert_caphi() ;
#define assert_caplo() CR = 0;
#define deassert_caplo() ;
#define get_comp() CompInp > CL ? 1 : 0

#elif defined(PORTENTA)
//** Note: Portenta GPIO interface methods are adapted from the Portenta GPIO HAL:
//https://github.com/arduino/portentax8-stm32h7-fw/blob/b2d8715d5a4619f4dc6ab258e1f1017789342ce4/libraries/STM32H7xx_HAL_Driver/Src/stm32h7xx_hal_gpio.c

#define assert_qequal() GPIOC->BSRR = GPIO_PIN_7
#define deassert_qequal() GPIOC->BSRR = (uint32_t)GPIO_PIN_7 << GPIO_NUMBER
#define assert_dacclr() GPIOC->BSRR = GPIO_PIN_6;
#define deassert_dacclr() GPIOC->BSRR = (uint32_t)GPIO_PIN_6 << GPIO_NUMBER
//Recall that capHi is actually capHib, an active LOW signal.
#define assert_caphi() GPIOJ->BSRR = (uint32_t)GPIO_PIN_11 << GPIO_NUMBER
#define deassert_caphi() GPIOJ->BSRR = GPIO_PIN_11
#define assert_caplo() GPIOG->BSRR = GPIO_PIN_7
#define deassert_caplo() GPIOG->BSRR = (uint32_t)GPIO_PIN_7 << GPIO_NUMBER
#define get_comp() ((GPIOK->IDR & GPIO_PIN_1) != 0x00U)

#elif defined(UNO)



#endif

// *** FE CONTROL MACROS ***

#if defined(PORTENTA)

#define assert_presamp() GPIOC->BSRR = GPIO_PIN_2
#define deassert_presamp() GPIOC->BSRR = (uint32_t)GPIO_PIN_2 << GPIO_NUMBER
#define assert_postsamp() GPIOH->BSRR = GPIO_PIN_15
#define deassert_postsamp() GPIOH->BSRR = (uint32_t)GPIO_PIN_15 << GPIO_NUMBER //Changed from C3
#define assert_rst() GPIOA->BSRR = GPIO_PIN_4
#define deassert_rst() GPIOA->BSRR = (uint32_t)GPIO_PIN_4 << GPIO_NUMBER

//PH15 should not be connected to anything.
#define NOP GPIOG->BSRR = GPIO_PIN_10;

#elif defined(UNO)
//The corresponding pins do not exist on the UNO
#define assert_presamp() ;
#define deassert_presamp() ;
#define assert_postsamp() ;
#define deassert_postsamp() ;
#define assert_rst() ;
#define deassert_rst() ;

#endif


// *** Unconditional macros ***



#define write_captrim_0(val) digitalWrite(D6, val); 
#define write_captrim_1(val) digitalWrite(D7, val); 
#define write_captrim_2(val) digitalWrite(D8, val);
#define write_captrim_3(val) digitalWrite(D9, val);
#define write_captrim_4(val) digitalWrite(D11, val);//Skip D10 which overlaps w/ D19.
#define write_captrim_5(val) digitalWrite(D12, val);
#define write_range2(val) digitalWrite(D13, val);
#define write_testen(val) digitalWrite(D14, val);


//All CDAC pulses should have a width of 90ns.
#define pulse_dacclr() \
  assert_dacclr(); NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP; \
  deassert_dacclr();

#define pulse_caphi() \
  assert_caphi(); NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;\
  deassert_caphi();

#define pulse_caplo() \
  assert_caplo(); NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP; \
  deassert_caplo();

#define pulse_qequal() \
  assert_qequal(); NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP; \
  deassert_qequal();

//Config register bits
char config[8] = { 0, 0, 0, 0, 0, 0,  //CapTrim<0:5>
                   0,                 //Range2
                   0
                 };               //TestEn


void setup() {
  // put your setup code here, to run once:
  Serial.begin(230400);
  set_config("");

#if defined(PORTENTA)
  //Configure pings as outputs.
  GPIO_Config(0b111100, 0b0);
  int output_pins[] = {D0,D1, D2, D3, D4, D5, D6, D7 , D8, D9, D11, D12, D13, D14, D19, D20, D21};
  for (int i = 0; i < 17; i++) {
    pinMode(output_pins[i], OUTPUT);
  }
  pinMode(D1, INPUT);
#endif

  CompInp = 0.5;
}

void loop() {


  //Accept and hand
  get_user_string(u);
  
  if (user_echo) {
    Serial.println(u);
  }

  //rc = REPORT CONFIG
if (u.substring(0, 6) == "echo:o") {
  user_echo = (u.substring(6, 1) == "n");

} else if (u == "rc") {
    report_config();
  //sc = SET CONFIG
 } else if (u.substring(0, 2) == "sc") {
    Serial.println("Setting new config...");
    set_config(u.substring(u.indexOf(':') + 1));
    report_config();
  }
  //emu = EMULATE CDAC OPERATION
  else if (u == "emu") {
    CompInp = 0;

    while (CompInp < 1) {
      do_conversion(data_array);


      print_data_big_endian(data_array, 10);
      Serial.println();

      CompInp = CompInp + 0.05;
    }
  }
  //stop = STOP; AWAIT RESET
  else if (u == "stop") {
    await_reset();
  } else if (u == "adcsmoke") {
    adc_smoke_test();
  } 
  else if (u == "deassert") {
      deassert_cdac_fe_signals();
    }
  else if (u == "presamp") {
      assert_presamp();
    }
  else if (u == "~presamp") {
      deassert_presamp();
    }
  else if (u == "sample") {
      assert_postsamp();
    }
  else if (u == "~sample") {
      deassert_postsamp();
    }
  else if (u == "rst") {
      assert_rst();
    }
  else if (u == "~rst") {
      deassert_rst();
    }
  else if (u == "cap") {
    serial_print_cap_values();
  } else if (u == "runfe*") {
    run_front_end();
  } else if (u == "IDN?") {
    Serial.print(DOCSTRING);
#ifdef PORTENTA
    Serial.print("PORTENTA ");
#endif
#ifdef UNO
    Serial.print("UNO ");
#endif
#ifdef EMULATOR
    Serial.print("EMU ");
#endif
    Serial.println();
  } else if (u == "PING") {
    Serial.println("PONG");
  } else if (u.substring(0, 5) == "cdac:") {
    Serial.println("Setting CDAC");
    cdac_cmd_str(u.substring(u.indexOf(':') + 1));
  } else if (u.substring(0, 9) == "cdac100x:") {
    cdac_100x(u.substring(u.indexOf(':') + 1));
  } else if (u.substring(0, 8) == "compinp:") {
    CompInp = atof(u.substring(u.indexOf(':') + 1).c_str());
  } else if (u == "conv100x") {
    do_conversion_100x();
  } else if (u == "conv") {
    do_conversion(data_array);
    print_data_big_endian(data_array, 10);
    Serial.println();
  } else if (u.substring(0, 7) == "convNx:") {
    //Serial.println("#hello world!")
    numConversions = atol(u.substring(u.indexOf(':') + 1).c_str());
    for (int i = 0; i < (1 + numConversions / 100); i++) {
      do_conversion_100x();
    }
  } else if (u == "samp100x") {
    do_sample_100x();
  } else if (u == "samp") {
    do_sample(data_array);
    print_data_big_endian(data_array, 10);
    Serial.println();
  } else if (u.substring(0, 7) == "sampNx:") {
    numConversions = atol(u.substring(u.indexOf(':') + 1).c_str());
    for (int i = 0; i < (1 + numConversions / 100); i++) {
      do_sample_100x();
    }
  } else if (u == "delay_demo") {
    delay_demo();
  }
}

//Pass a null string to initialize to whatever is already stored in memory.
void set_config(String config_str) {
  for (int i = 0; i < config_str.length(); i++) {
    if (config_str[i] == '0') config[i] = 0;
    else config[i] = 1;
  }

  write_captrim_0(config[0]);
  write_captrim_1(config[1]);
  write_captrim_2(config[2]);
  write_captrim_3(config[3]);
  write_captrim_4(config[4]);
  write_captrim_5(config[5]);
  write_range2(config[6]);
  write_testen(config[7]);
}

void report_config() {
  Serial.print("Config is: ");
  print_data(config, 8);
  Serial.println("");
}


void serial_print_cap_values() {
  Serial.print("CompInp: ");
  Serial.print(CompInp);
  Serial.print(" CL: ");
  Serial.print(CL);
  Serial.print(" CR: ");
  Serial.println(CR);
}

/**
   do_conversion - performs a single SAR ADC conversion and returns the data as a binary array.

*/
void do_conversion(char* data) {

  int capseq = 10;
  int current_precision = 9;

  noInterrupts();
  //For all 9 bits of data to collect.
  for (int i = 9; i >= 0; i--) {

    //Go through all previous data, using the value to
    //assert caphi or caplo.
    for (int k = i; k <= 9; k++) {
      //At the beginning of the calculation only, assert dacclr.
      if (k == i) {
        //Serial.println("DACclr!");
        assert_dacclr();NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;  //0ns
        assert_caphi(); NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;  //30ns
        NOP;              //60ns
        deassert_dacclr();NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;//90ns  --> DACclr PW = 90ns
        deassert_caphi(); NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;//120ns --> caphib PW = 90ns
      } else if (data[k] == 1) {
        assert_caphi();NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;
        NOP;
        NOP;
        deassert_caphi();NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP; // --> caphib PW = 90ns
      } else {
        assert_caplo();NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;
        NOP;
        NOP;
        deassert_caplo();NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP; // --> caphib PW = 90ns
      }

      //Serial.print("Capclk ~ ");
      //serial_print_cap_values();
      assert_qequal();NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;
      NOP;
      NOP;
      deassert_qequal();NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP; // --> Qequal PW = 90ns
      //Serial.print("Qequal ~ ");
      //serial_print_cap_values();
    }

    NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;
    data[i] = get_comp();
    NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;
    //Serial.print("Recorded ");
    //Serial.println(int(data[i]));
  }
  interrupts();
}
/** do_conversion_100x - runs do_conversion() 100 times and saves the data in a
    100-entry buffer.
*/
void  do_conversion_100x() {
  for (int i = 0; i < 100; i++) {
    do_conversion(data_array);
    delayMicroseconds(5); 
    data_buffer[i] = bin_array_to_dec_big_endian(data_array, 10);
  }

  //Serial.println("did convs!");
  String measurements = String();
  for (int i = 0; i < 100; i++) {
    measurements += String(data_buffer[i], DEC) + String("\n");
    //Serial.println(data_buffer[i]);
  }
//  Serial.println("-------------------------");
  Serial.print(measurements); //println has hardcoded \r\n (sic!)
  //Serial.print("\n");
}

void deassert_cdac_fe_signals() {
  //Zero out PreSamp, PostSamp, Rst.
  deassert_presamp();
  deassert_postsamp();
  deassert_rst();

  //Deassert all CDAC signals.
  deassert_caphi();
  deassert_caplo();
  deassert_qequal();
  deassert_dacclr();
}

void adc_smoke_test() {
  //Set up config (CapTrim=Nominal, TestEn=1)
  set_config("00000101");
  report_config();

  deassert_cdac_fe_signals();

  Serial.println("CapTrim=Nom; Ready to begin!");
  get_user_string(u);

  for (int k = 0; k < 2; k++) {
    for (int i = 1; i < 4; i++) {
      pulse_dacclr();

      pulse_caphi();
      pulse_qequal();

      if (i == 1) Serial.println("Expected voltage: 0.5 Vref");

      if (i == 2) {
        pulse_caphi();
        pulse_qequal();
        Serial.println("Expected voltage: 0.75 Vref");
      }

      if (i == 3) {
        pulse_caplo();
        pulse_qequal();
        Serial.println("Expected voltage: 0.25 Vref");
      }
      get_user_string(u);
    }
    set_config("11111101");
    report_config();
    Serial.println("CapTrim=Hi; Ready to begin!");
    get_user_string(u);
  }
}

void cdac_cmd_str(String cmd_str) {

  for (int i = 0; i < cmd_str.length(); i++) {
    if (cmd_str[i] == '0') data_array[i] = 0;
    else data_array[i] = 1;
  }

  cdac_cmd(data_array);
}

//Run a CDAC 100 times and print the output from Comp to Serial.
void cdac_100x(String cmd_str) {
  for (int i = 0; i < cmd_str.length(); i++) {
    if (cmd_str[i] == '0') data_array[i] = 0;
    else data_array[i] = 1;
  }

  for (int i = 0; i < 100; i++) {
    cdac_cmd(data_array);
    NOP;NOP;NOP; NOP;NOP;NOP;NOP;NOP;NOP;NOP;
    Serial.print(get_comp());NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;
  }
  Serial.println();
}


void cdac_cmd(char* data_array) {
  deassert_cdac_fe_signals();

  pulse_dacclr();NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;

  //Start from the lowest bit.
  //Do 10->1 instead of 9->0 to avoid having to deal with
  //overflow comparisons.
  for (int i = 10; i > 0; i--) {
    if (data_array[i - 1] > 0) {
      pulse_caphi();NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;
    } else {
      pulse_caplo();NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;
    }
    pulse_qequal();NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;NOP;
  }
}

/** Executes one sample, including reset, sampling, and conversion phases.
 *  Stores the result in the provided char*.
 */
void do_sample(char* data) {
  noInterrupts();
  assert_rst();       //0ns
  for(uint8_t i = 0; i < 29; i++) NOP; //870ns
  deassert_rst();     //900ns --> Reset PW = 900 ns
  assert_presamp();   //930ns
  assert_postsamp();  //960ns
  NOP;NOP;NOP;NOP;NOP;NOP;NOP;//1200 ns
  deassert_presamp(); //1200 ns --> PW(Postsamp^ --> Presampv) = 240ns
  NOP;NOP;NOP; NOP;NOP;NOP; NOP;NOP;NOP; //1470ns
  deassert_postsamp();//1500 ns --> PW(Presampv --> Postsampv) = 300ns

  //This should already have interrupts disabled but just in case...
  do_conversion(data);
  interrupts();
}

void do_sample_100x() {
  for (int i = 0; i < 100; i++) {
    do_sample(data_array);
    data_buffer[i] = bin_array_to_dec_big_endian(data_array, 10);
  }

  for (int i = 0; i < 100; i++) {
    Serial.println(data_buffer[i]);
  }
}

void run_front_end() {
  long sample_ct;

  deassert_cdac_fe_signals();

  while (!Serial.available()) {

    for (long i = 0; i < 10000; i++) {

      //TBD: Check the Portenta timing on this!!!
      //assert_postsamp();
      //assert_presamp();
      //deassert_presamp();
      //deassert_postsamp();
      noInterrupts();
      assert_rst();       //0ns
      for(uint8_t i = 0; i < 29; i++) NOP; //870ns
      deassert_rst();     //900ns --> Reset PW = 900 ns
      assert_postsamp();   //930ns
      assert_presamp();  //960ns
      NOP;NOP;NOP;NOP;NOP;NOP;NOP;//1200 ns
      deassert_postsamp(); //1200 ns --> PW(Postsamp^ --> Presampv) = 240ns
      NOP;NOP;NOP; NOP;NOP;NOP; NOP;NOP;NOP; //1470ns
      deassert_presamp();//1500 ns --> PW(Presampv --> Postsampv) = 300ns
      interrupts();
      
      delayMicroseconds(10);
      //assert_rst();
      //deassert_rst();
    }

    sample_ct++;
    Serial.print(sample_ct * 10);
    Serial.println(" k samples taken...");
  }
}

void delay_demo() {
  volatile int i;

  while (1) {

    deassert_dacclr();
    delay(1);
    if (Serial.available()) break;

    noInterrupts();
    assert_dacclr();
    deassert_dacclr();
    NOP;
    assert_dacclr();
    NOP;
    deassert_dacclr();
    NOP;
    assert_dacclr();
    NOP;
    NOP;
    deassert_dacclr();
    NOP;
    assert_dacclr();
    NOP; NOP; NOP;
    deassert_dacclr();
    NOP; NOP;
    interrupts();
  }

}

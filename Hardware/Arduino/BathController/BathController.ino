#include <DHT.h>
#include "IRTemp.h"

#define HV_PIN 13
// Fits 16mhz scalar with 0.0% error
// faster is better for nested interrupt
// http://wormfood.net/avrbaudcalc.php
#define SERIAL_BAUD 250000

#define ENV_TEMP_PIN      2
#define BATH_TEMP_PIN     A0 
#define BATH_TEMP_SAMPLES 5
#define BATH_BCOEFFICIENT 3900
#define BATH_TEMP_RESIST  10000 

#define TEMPERATURE_REQUEST 0x11      // DC1
#define SET_ELEMENT_REQUEST 0x12      // DC2
#define SUCCESS_ACCEPT      0x06      // ACK
#define READY_REQUEST       0x05      // ENQ
#define FAIL_DENY           0x15      // NAK
#define EMERGENCY_STOP      0x18      // CAN
#define TEMPERATURE_SCALE    100      // Scale to int

#define PKT_SZ               64
#define PKT_BUFFER_SZ       128      

// Saftey interlocks
static const boolean interlocks = true;
boolean interlock_triggered = false;
// IR sensor
static const byte PIN_DATA     = 8;
static const byte PIN_CLOCK    = 9;
static const byte PIN_ACQUIRE  = 10;
static const TempUnit IR_UNIT = CELSIUS;

boolean sending = false;

boolean element_on = false;
unsigned long off_time = 0;
unsigned long last_sample = 0;

volatile float fusion_bath_temp = 0;
volatile float last_temp = 0;
volatile uint8_t timer1_counter;
volatile uint8_t count;

DHT env_temp(ENV_TEMP_PIN, DHT22);
IRTemp ir_temp(PIN_ACQUIRE, PIN_CLOCK, PIN_DATA);

void setup() {
  pinMode(HV_PIN, OUTPUT);
  digitalWrite(HV_PIN, LOW);
  cli();           // disable all interrupts
  TCCR1A = 0;
  TCCR1B = 0;
  timer1_counter = 34286;   // preload timer 65536-16MHz/256/2Hz
  TCNT1 = timer1_counter;   // preload timer
  TCCR1B |= (1 << CS12);    // 256 prescaler 
  TIMSK1 |= (1 << TOIE1);   // enable timer overflow interrupt
  sei();             // enable all interrupts
  Serial.begin(SERIAL_BAUD);
  env_temp.begin();
  // TODO: prime filter with an avg'd themistor value
  fusion_bath_temp = (sample_bath_temp() + sample_bath_temp()) / 2.0;
  last_temp = fusion_bath_temp;
}

void loop() {
  if(Serial.available() > 0){
    TIMSK1 &= ~(1 << TOIE1);
    uint8_t b = Serial.read();
    if(b == READY_REQUEST){
      // Acknowledge request
      sending = true;
      Serial.write(SUCCESS_ACCEPT);
      Serial.flush();
      // Blocking wait reply - make timeout
      while(Serial.available() <= 0);
      b = Serial.read();
      if(b == TEMPERATURE_REQUEST){
        Serial.write(SUCCESS_ACCEPT);
        uint8_t pkt[PKT_BUFFER_SZ] = "";
        pack_temps(pkt, env_temp.readTemperature(), sample_bath_temp());
        for(int i = 0; i < PKT_SZ; i++){
          Serial.write(pkt[i]);
        }
        while(Serial.available() <= 0);
        b = Serial.read();
        // If the packet was corrupt
        if(b != SUCCESS_ACCEPT){
          // Assume the worst, shut off
          digitalWrite(HV_PIN, LOW);
          interlock();
        }
        clear_comms();
      }
      else if(b == SET_ELEMENT_REQUEST){
        // Acknowledge request
        Serial.write(SUCCESS_ACCEPT);
        // Annoying arduino bug (<= 1.6.5),compiler wants this to
        // be uint32_t here, can't use uint8_t and recast @ bitwise
        uint32_t bugfix[5];
        // Normal packet..
        uint8_t pkt[PKT_BUFFER_SZ];
        while(Serial.available() < (PKT_SZ - 1));
        // Get out the element time
        for(int i = 0; i < 4; i++){ 
          bugfix[i] = Serial.read();
          // Copy over as 8bit.. :/
          pkt[i] = (uint8_t)bugfix[i];
        }
        // Get the rest of the packet data
        for(int i = 4; i < PKT_SZ; i++){ 
          pkt[i] = Serial.read();
        }
        // Assemble element time
        uint32_t total = (uint32_t)(bugfix[0] << 24)|
                         (uint32_t)(bugfix[1] << 16)|
                         (uint32_t)(bugfix[2] <<  8)|
                         (uint32_t)(bugfix[3]);
        // Extract checksum
        uint8_t csum = pkt[PKT_SZ - 1];
        if(csum == checksum(pkt)){
          // Acknowledge reciept
          Serial.write(SUCCESS_ACCEPT);
          digitalWrite(HV_PIN, HIGH);  
          element_on = true;
          off_time = millis() + total;
        } else {
          // Announce failure
          Serial.write(FAIL_DENY);
          digitalWrite(HV_PIN, LOW);
          interlock_triggered = true;
          interlock();
        }
        // Cleanup
        clear_comms();
      }
      // Wasn't a known request, bump it
      else {
        clear_comms();
        Serial.write(FAIL_DENY);
        interlock_triggered = true;
        interlock();
      }
    // Wasn't ready req, bump it
    } else {
      clear_comms();
      Serial.write(FAIL_DENY);
      interlock_triggered = true;
      interlock();
   }
  } 
  if(element_on && (off_time <= millis())){
    digitalWrite(HV_PIN, LOW);
    element_on = false;
  }
  Serial.flush();
  sending = false;
}


ISR(TIMER1_OVF_vect)        // interrupt service routine 
{
  // Get out of the way of incoming serial
  // nesting doesn't quite cut it on recv
  if(Serial.available() > 0 || sending) return;
  // Nest any outgoing serial in the buffer
  sei();
  count++;
  if(count >= 2){
    uint16_t dt = last_sample - millis();
    last_sample = millis();
    TCNT1 = timer1_counter;   // preload timer
    float r = ir_temp.getIRTemperature(IR_UNIT);
    if(isnan(r)){r = 0;}
    float t_delta = ((r - last_temp) / dt);
    fusion_bath_temp = temperature_fusion(t_delta, sample_bath_temp(), float(dt/1000), fusion_bath_temp);
    count = 0;
  }
  // Just incase
  if(interlock_triggered){
    interlock();
  }
}


void interlock(void){
  if(interlocks){
    TIMSK1 &= ~(1 << TOIE1);
    digitalWrite(HV_PIN, LOW);
    while(true){
      Serial.write(FAIL_DENY);
      delay(500);
    }
  }
}


float sample_bath_temp(){
  float steinhart = 0;
  long long total = 0;
  float average = 0;
  for (int i=0; i< BATH_TEMP_SAMPLES; i++) {
   total += analogRead(BATH_TEMP_PIN);
   delay(10);
  }
  average = total/BATH_TEMP_SAMPLES;
  average = 1023 / average - 1;
  average = BATH_TEMP_RESIST / average; // Resistance
  steinhart = average / 10000;          // nominal thermistor (R/Ro)
  steinhart = log(steinhart);           // ln(R/Ro)
  steinhart /= BATH_BCOEFFICIENT;       // 1/B * ln(R/Ro)
  steinhart += 1.0 / (25 + 273.15);     // + (1/To)
  steinhart = 1.0 / steinhart;          // Invert
  return (steinhart - 273.15);          // convert to C
}

float temperature_fusion(float integral_temp, float noisey_temp, 
                         float dt,            float fusion_temp){
  // A complimentary filter for temperature. Intended to fuse stable temperature
  // change from IR temp sensor with fast update of thermistor.
  // integral_temp = IR temperature change as deg/sec
  // noisey_temp = Thermistor temperature
  // fusion_temp = Variable this function updates
  // dt = time delta in millis
  return (0.99)*(fusion_temp+(integral_temp*dt))+(0.01)*(noisey_temp);
}

void clear_comms(){
  while(Serial.available() > 0){
    Serial.read();
  }
}

void pack_temps(uint8_t* packet, float env_temp, float bath_temp){
  // Pack scaled temperatures into packet, re-calc checksum
  uint16_t e = env_temp  * TEMPERATURE_SCALE;
  uint16_t b = bath_temp * TEMPERATURE_SCALE;
  packet[0]  = (e >> 8) & 0xFF;
  packet[1]  = e & 0xFF;
  packet[2]  = (b >> 8) & 0xFF;
  packet[3]  = b & 0xFF;
  packet[63] = checksum(packet);
}


uint8_t checksum(uint8_t* packet){
  uint32_t t = 0;
  for(int i = 0; i < 63; i++){
   t += packet[i];
  }
  return (unsigned)t%255;
}


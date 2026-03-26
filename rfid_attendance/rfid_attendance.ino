//Arduino Code - RC522 Read RFID Tag UID
#include <Wire.h>          // ADD THIS
#include <LiquidCrystal_I2C.h>  // ADD THIS
#include <SPI.h>
#include <MFRC522.h>
 
 /*
 * Typical pin layout used:
 * --------------------------------------- 
 *             MFRC522      Arduino       
 *             Reader/PCD   Uno/101       
 * Signal      Pin          Pin           
 * ---------------------------------------
 * RST/Reset   RST          7            
 * SPI SS      SDA(SS)      10            
 * SPI MOSI    MOSI         11 / ICSP-4   
 * SPI MISO    MISO         12 / ICSP-1   
 * SPI SCK     SCK          13 / ICSP-3   
*/
#define SS_PIN 10
#define RST_PIN 7
 
MFRC522 rfid(SS_PIN, RST_PIN); // Instance of the class
LiquidCrystal_I2C lcd(0x27, 16, 2);  // ADD THIS
 
MFRC522::MIFARE_Key key; 
 
void setup() { 
  Serial.begin(9600);
  SPI.begin(); // Init SPI bus
  rfid.PCD_Init(); // Init RC522 vxxxf
  Wire.begin();
  lcd.init();
  lcd.backlight();
  lcd.setCursor(0, 0);
  lcd.print("OPTI System");
  lcd.setCursor(0, 1);
  lcd.print("Ready to scan");
  
}
void loop() {
  if (Serial.available()) {
  String response = Serial.readStringUntil('\n');
  response.trim();
  int sep = response.indexOf('|');
  if (sep != -1) {
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print(response.substring(0, sep));
    lcd.setCursor(0, 1);
    lcd.print(response.substring(sep + 1));
    delay(2500);
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("OPTI System");
    lcd.setCursor(0, 1);
    lcd.print("Ready to scan");
  }
}
 
  // Reset the loop if no new card present on the sensor/reader. This saves the entire process when idle.
  if ( ! rfid.PICC_IsNewCardPresent())
    return;
 
  // Verify if the NUID has been readed
  if ( ! rfid.PICC_ReadCardSerial())
    return;
 
  MFRC522::PICC_Type piccType = rfid.PICC_GetType(rfid.uid.sak);
 
  Serial.print(F("RFID Tag UID:"));
  printHex(rfid.uid.uidByte, rfid.uid.size);
  Serial.println("");
 
  rfid.PICC_HaltA(); // Halt PICC
}
 
//Routine to dump a byte array as hex values to Serial. 
void printHex(byte *buffer, byte bufferSize) {
  for (byte i = 0; i < bufferSize; i++) {
    Serial.print(buffer[i] < 0x10 ? " 0" : " ");
    Serial.print(buffer[i], HEX);
  }
}

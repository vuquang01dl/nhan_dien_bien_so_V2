#include <SPI.h>
#include <MFRC522.h>
#include <Servo.h>

Servo myservo;  // Tạo đối tượng servo để điều khiển servo

int pos = 0;  // Biến lưu vị trí của servo

#define RST_PIN 9
#define SS_PIN 10
char receivedChar;  // Biến lưu ký tự nhận được từ cổng serial

MFRC522 mfrc522(SS_PIN, RST_PIN);

void setup() {
  myservo.attach(5);  // Kết nối servo tại chân số 5
  myservo.write(10);  // Đặt servo ở góc 90 độ (vị trí đóng)

  Serial.begin(9600);

  SPI.begin();
  mfrc522.PCD_Init();

}

void mo_barie() {
    // Đóng barrier
  for (pos = 10; pos <= 100; pos += 1) {  // Góc từ 0 đến 90
    myservo.write(pos);
    delay(15);  // Chờ servo di chuyển
  }


  delay(3000);  // Giữ barrier mở trong 3 giây
  // Mở barrier
  for (pos = 100; pos >= 10; pos -= 1) {  // Góc từ 90 đến 0
    myservo.write(pos);
    delay(15);  // Chờ servo di chuyển
  }

}

void loop() {
  // Kiểm tra dữ liệu nhận từ cổng Serial
  if (Serial.available() > 0) {
    receivedChar = Serial.read();  // Đọc ký tự từ Serial

    if (receivedChar == 'A') {  // Nếu nhận được ký tự 'B'
      mo_barie();  // Gọi hàm mở barrier
    }
  }

  // Kiểm tra thẻ RFID
  if (!mfrc522.PICC_IsNewCardPresent()) {
    return;
  }

  if (!mfrc522.PICC_ReadCardSerial()) {
    return;
  }

  // In UID của thẻ ra Serial
  for (byte i = 0; i < mfrc522.uid.size; i++) {
    Serial.print(mfrc522.uid.uidByte[i] < 0x10 ? " 0" : " ");
    Serial.print(mfrc522.uid.uidByte[i], HEX);
  }
  Serial.println("");
  mfrc522.PICC_HaltA();
  mfrc522.PCD_StopCrypto1();
}

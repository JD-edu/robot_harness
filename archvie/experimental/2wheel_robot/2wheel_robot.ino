/* Chapter 15: L298P motor shield controller for Arduino Uno.
 * Protocol: $M,LLLL,RRRR# followed by a newline.
 * Shield pin mapping verified on the target hardware:
 *   Left (motor A):  DIR_A=D12, PWM_A=D10
 *   Right (motor B): DIR_B=D13, PWM_B=D11
 */

#include <Arduino.h>

constexpr uint8_t PIN_DIR_A = 12;
constexpr uint8_t PIN_PWM_A = 10;
constexpr uint8_t PIN_DIR_B = 13;
constexpr uint8_t PIN_PWM_B = 11;

constexpr uint8_t FRAME_LENGTH = 13;
constexpr unsigned long COMMAND_TIMEOUT_MS = 500;

char frame[FRAME_LENGTH + 1];
uint8_t frame_index = 0;
unsigned long last_command_ms = 0;

// ASCII '0'..'9','A'..'F' 한 글자를 0..15로 변환합니다.
int8_t hexDigit(char value) {
  if (value >= '0' && value <= '9') return value - '0';
  if (value >= 'A' && value <= 'F') return value - 'A' + 10;
  if (value >= 'a' && value <= 'f') return value - 'a' + 10;
  return -1;
}

bool parseHex16(const char* text, int16_t& result) {
  uint16_t value = 0;
  for (uint8_t i = 0; i < 4; ++i) {
    const int8_t digit = hexDigit(text[i]);
    if (digit < 0) return false;
    value = static_cast<uint16_t>((value << 4) | digit);
  }
  result = static_cast<int16_t>(value);
  return true;
}

void driveMotor(uint8_t dir_pin, uint8_t pwm_pin, int16_t command) {
  command = constrain(command, -255, 255);
  digitalWrite(dir_pin, command >= 0 ? HIGH : LOW);
  analogWrite(pwm_pin, abs(command));
}

void stopMotors() {
  analogWrite(PIN_PWM_A, 0);
  analogWrite(PIN_PWM_B, 0);
}

bool applyFrame(const char* data) {
  if (data[0] != '$' || data[1] != 'M' || data[2] != ',' ||
      data[7] != ',' || data[12] != '#') {
    return false;
  }
  int16_t left = 0;
  int16_t right = 0;
  if (!parseHex16(data + 3, left) || !parseHex16(data + 8, right)) {
    return false;
  }
  driveMotor(PIN_DIR_A, PIN_PWM_A, left);
  driveMotor(PIN_DIR_B, PIN_PWM_B, right);
  last_command_ms = millis();
  return true;
}

void setup() {
  pinMode(PIN_DIR_A, OUTPUT);
  pinMode(PIN_PWM_A, OUTPUT);
  pinMode(PIN_DIR_B, OUTPUT);
  pinMode(PIN_PWM_B, OUTPUT);
  stopMotors();
  Serial.begin(115200);
  last_command_ms = millis();
}

void loop() {
  while (Serial.available() > 0) {
    const char incoming = static_cast<char>(Serial.read());
    if (incoming == '$') {
      frame_index = 0;
      frame[frame_index++] = incoming;
    } else if (frame_index > 0 && frame_index < FRAME_LENGTH) {
      frame[frame_index++] = incoming;
      if (frame_index == FRAME_LENGTH) {
        frame[FRAME_LENGTH] = '\0';
        applyFrame(frame);
        frame_index = 0;
      }
    }
  }

  if (millis() - last_command_ms > COMMAND_TIMEOUT_MS) {
    stopMotors();
  }
}

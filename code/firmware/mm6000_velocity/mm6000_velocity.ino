#include <AccelStepper.h>
#include <Servo.h>
#include <stdlib.h>   // strtod, atoi (avr-libc float sscanf is unsupported)

// --- CNC Shield V3 pin map (A4988 drivers) ---
#define X_STEP 2
#define X_DIR  5
#define Y_STEP 3
#define Y_DIR  6
#define ENABLE 8      // active LOW: energizes all drivers
#define SERVO_PIN 11

// --- machine constants (match mm6000.ino) ---
#define STEPS_PER_MM_X 5.0
#define STEPS_PER_MM_Y 5.0
#define ACCEL 2000.0            // steps/s^2: bounds how fast commanded speed slews
#define MAX_STEP_SPEED 4000.0   // steps/s hard cap per axis

// --- safety ---
#define WATCHDOG_MS 200         // no V within this -> ramp to zero
#define SOFT_LIMIT_MM 90.0      // +/- travel from startup origin
const long LIMIT_STEPS_X = (long)(SOFT_LIMIT_MM * STEPS_PER_MM_X);
const long LIMIT_STEPS_Y = (long)(SOFT_LIMIT_MM * STEPS_PER_MM_Y);

AccelStepper xAxis(AccelStepper::DRIVER, X_STEP, X_DIR);
AccelStepper yAxis(AccelStepper::DRIVER, Y_STEP, Y_DIR);
Servo clickServo;

char buf[48];
uint8_t len = 0;

float targetSpeedX = 0, targetSpeedY = 0;   // steps/s setpoint from last V
float currentSpeedX = 0, currentSpeedY = 0; // slewed actual command
unsigned long lastCmdMillis = 0;
unsigned long lastMicros = 0;

void setup() {
  pinMode(ENABLE, OUTPUT);
  digitalWrite(ENABLE, LOW);   // enable drivers
  xAxis.setMaxSpeed(MAX_STEP_SPEED);
  yAxis.setMaxSpeed(MAX_STEP_SPEED);
  xAxis.setCurrentPosition(0); // origin = bed center reference
  yAxis.setCurrentPosition(0);
  clickServo.attach(SERVO_PIN);
  clickServo.write(90);        // rest angle
  Serial.begin(115200);
  lastMicros = micros();
  lastCmdMillis = millis();
  Serial.println("mm6000v ready");
}

float clampSpeed(float s) {
  if (s > MAX_STEP_SPEED) return MAX_STEP_SPEED;
  if (s < -MAX_STEP_SPEED) return -MAX_STEP_SPEED;
  return s;
}

// Move currentSpeed toward targetSpeed, limited to maxDelta steps/s this tick.
float slew(float current, float target, float maxDelta) {
  if (target > current) {
    current += maxDelta;
    if (current > target) current = target;
  } else if (target < current) {
    current -= maxDelta;
    if (current < target) current = target;
  }
  return current;
}

void handleVelocity(char *args) {
  char *p = args;
  float vx = strtod(p, &p);
  float vy = strtod(p, &p);
  targetSpeedX = clampSpeed(vx * STEPS_PER_MM_X);
  targetSpeedY = clampSpeed(vy * STEPS_PER_MM_Y);
  lastCmdMillis = millis();
  // no ack: this is the streaming hot path
}

void handleServo(char *args) {
  int angle = atoi(args);
  if (angle < 0) angle = 0;
  if (angle > 180) angle = 180;
  clickServo.write(angle);
  Serial.println("ok");
}

void handleLine(char *line) {
  if (line[0] == 'V') {
    handleVelocity(line + 1);
  } else if (line[0] == 'S') {
    handleServo(line + 1);
  } else {
    Serial.println("err");
  }
}

void readSerial() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '!') {              // realtime abort: stop commanding motion
      targetSpeedX = 0;
      targetSpeedY = 0;
      len = 0;                   // discard any partial line
      continue;
    }
    if (c == '\n') {
      buf[len] = '\0';
      if (len > 0) handleLine(buf);
      len = 0;
    } else if (len < sizeof(buf) - 1) {
      buf[len++] = c;
    }
  }
}

void loop() {
  readSerial();

  // watchdog: host went quiet -> command zero (slew still ramps it down)
  if (millis() - lastCmdMillis > WATCHDOG_MS) {
    targetSpeedX = 0;
    targetSpeedY = 0;
  }

  unsigned long now = micros();
  float dt = (now - lastMicros) / 1000000.0;
  lastMicros = now;
  if (dt <= 0) dt = 0.0001;
  float maxDelta = ACCEL * dt;   // steps/s of speed change allowed this tick

  currentSpeedX = slew(currentSpeedX, targetSpeedX, maxDelta);
  currentSpeedY = slew(currentSpeedY, targetSpeedY, maxDelta);

  // firmware-authoritative soft limits: if at edge and pushing further, stop axis
  long px = xAxis.currentPosition();
  if ((px <= -LIMIT_STEPS_X && currentSpeedX < 0) ||
      (px >=  LIMIT_STEPS_X && currentSpeedX > 0)) {
    currentSpeedX = 0;
  }
  long py = yAxis.currentPosition();
  if ((py <= -LIMIT_STEPS_Y && currentSpeedY < 0) ||
      (py >=  LIMIT_STEPS_Y && currentSpeedY > 0)) {
    currentSpeedY = 0;
  }

  xAxis.setSpeed(currentSpeedX);
  yAxis.setSpeed(currentSpeedY);
  xAxis.runSpeed();              // non-blocking: one step if due
  yAxis.runSpeed();
}

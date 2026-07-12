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

// --- machine constants (measure steps/mm on the built rig, then set) ---
#define STEPS_PER_MM_X 5.0    // full-step: 200 steps/rev / 40mm GT2-20T rev
#define STEPS_PER_MM_Y 5.0    // no microstep jumpers; coarse 0.2mm/step
#define ACCEL 2000.0            // steps/s^2
#define DEFAULT_SPEED 1000.0    // steps/s fallback if feed missing/zero

AccelStepper xAxis(AccelStepper::DRIVER, X_STEP, X_DIR);
AccelStepper yAxis(AccelStepper::DRIVER, Y_STEP, Y_DIR);
Servo clickServo;

char buf[48];
uint8_t len = 0;

void setup() {
  pinMode(ENABLE, OUTPUT);
  digitalWrite(ENABLE, LOW);   // enable drivers
  xAxis.setAcceleration(ACCEL);
  yAxis.setAcceleration(ACCEL);
  xAxis.setMaxSpeed(DEFAULT_SPEED);
  yAxis.setMaxSpeed(DEFAULT_SPEED);
  clickServo.attach(SERVO_PIN);
  clickServo.write(90);        // rest angle
  Serial.begin(115200);
  Serial.println("mm6000 ready");
}

// Run both axes to their targets. Returns early if a '!' arrives mid-move.
void runMove() {
  while (xAxis.distanceToGo() != 0 || yAxis.distanceToGo() != 0) {
    if (Serial.available() && Serial.peek() == '!') {
      Serial.read();           // consume the '!'
      xAxis.stop();
      yAxis.stop();
      xAxis.setCurrentPosition(xAxis.currentPosition());
      yAxis.setCurrentPosition(yAxis.currentPosition());
      return;
    }
    xAxis.run();
    yAxis.run();
  }
}

void handleJog(char *args) {
  float dx = 0, dy = 0, feed = 0;
  // args: "<dx_mm> <dy_mm> <feed_mm_min>"
  char *p = args;
  dx = strtod(p, &p);
  dy = strtod(p, &p);
  feed = strtod(p, &p);
  float sx = feed > 0 ? (feed / 60.0) * STEPS_PER_MM_X : DEFAULT_SPEED;
  float sy = feed > 0 ? (feed / 60.0) * STEPS_PER_MM_Y : DEFAULT_SPEED;
  xAxis.setMaxSpeed(sx);
  yAxis.setMaxSpeed(sy);
  xAxis.move((long)lround(dx * STEPS_PER_MM_X));
  yAxis.move((long)lround(dy * STEPS_PER_MM_Y));
  runMove();
  Serial.println("ok");
}

void handleServo(char *args) {
  int angle = atoi(args);
  if (angle < 0) angle = 0;
  if (angle > 180) angle = 180;
  clickServo.write(angle);
  Serial.println("ok");
}

void handleLine(char *line) {
  if (line[0] == 'J') {
    handleJog(line + 1);
  } else if (line[0] == 'S') {
    handleServo(line + 1);
  } else {
    Serial.println("err");
  }
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '!') {            // realtime abort when idle: nothing to stop
      xAxis.stop();
      yAxis.stop();
      len = 0;                 // discard any partial line
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

# _Mouse Mover 6000_
An XY plotter based system that can control the movement and clicks of your computer mouse in order to *help* one play shooter based video games by assisting aim.

## _Image Gallery_
<img width="1119" height="665" alt="mm6 image 1" src="https://github.com/user-attachments/assets/918a0417-caf0-4016-a666-a7f2a608fe40" />
<img width="943" height="558" alt="mm6 image 5" src="https://github.com/user-attachments/assets/ea8b6b45-db09-474e-af5c-e4d805f1a15d" />
<img width="879" height="355" alt="mm6 image 2" src="https://github.com/user-attachments/assets/968aeb85-c7f1-4e76-987c-5b29a6f8b62d" />
<img width="946" height="388" alt="mm6 image 3" src="https://github.com/user-attachments/assets/b5b2995f-b22c-4685-99d8-a65c99ffaaf2" />
<img width="875" height="770" alt="mm6 image 4" src="https://github.com/user-attachments/assets/f58645ee-d676-4509-a19c-8337f3116ffb" />
<img width="1920" height="1079" alt="mm6 detection code" src="https://github.com/user-attachments/assets/5fe688be-93d7-4a38-ae77-853f87bf1b5f" />
<img width="4032" height="3024" alt="IMG_5696" src="https://github.com/user-attachments/assets/7d795dc6-7cbf-4cd5-9246-c2091f83d33a" />
<img width="4032" height="3024" alt="IMG_5695" src="https://github.com/user-attachments/assets/8013aecb-5231-4ef4-85ad-8c61b2be667f" />
<img width="4032" height="3024" alt="IMG_5694" src="https://github.com/user-attachments/assets/e3af6ea3-4113-4ed5-ad75-7cb3672e4039" />
<img width="4032" height="3024" alt="IMG_5693" src="https://github.com/user-attachments/assets/7bed4775-5df2-4fd8-b679-bb4a6435c3c6" />



## _How it Works_
A color-detection pipeline screenshots the display, finds the on-screen targets, and picks the one nearest the crosshair. The target's pixel offset from screen center is turned into a **velocity command** and streamed continuously over USB to an Arduino Uno + CNC Shield V3 running custom firmware (`code/firmware/mm6000_velocity/`).

The firmware runs the two NEMA 17 steppers at that commanded speed, ramping smoothly between updates instead of stopping every frame — so the mouse glides toward the target rather than moving in choppy hops. Once the crosshair is on the target, the SG90 servo clicks. Then it repeats for the next-nearest target.

> **Note:** the rig originally ran GRBL/G-code; that path was replaced by the custom velocity firmware. The old position-based (move-and-settle) driver is kept for reference in [`archive/stop-start-driver/`](archive/stop-start-driver/).

## _Setup & Run_
Steps to run on a fresh machine.

**1. Firmware** — open `code/firmware/mm6000_velocity/mm6000_velocity.ino` in the Arduino IDE, install the **AccelStepper** and **Servo** libraries, select the Uno + its port, and Upload. The Serial Monitor (115200 baud) should print `mm6000v ready`. Center the carriage before powering — power-on position is the origin.




Machine constants to check in the sketch before flashing:
```
STEPS_PER_MM_X/Y  5.0     // steps per mm — measure on your rig
SOFT_LIMIT_MM     90.0    // ± travel from the power-on origin
ACCEL             4000.0  // slew rate (higher = snappier, too high = jerky)
WATCHDOG_MS       600     // firmware ramps to 0 if the host goes quiet
```

**2. Python** —
```
cd code
pip install -r requirements.txt        # optional: pip install dxcam (faster capture)
```

**3. Configure** `code/aimplotter/config.py` — set `port` (your Arduino COM port), `screen_region`/`screen_center` for your display, and `hsv_lower`/`hsv_upper` for the target color.

**4. Calibrate `gain`** (mm of travel per pixel of view shift) — aim at a target and run:
```
python -m aimplotter.velocity_calibrate
```
Press ENTER; the carriage drives a known velocity for a known time, measures the pixel shift, and prints a suggested `config.gain`. Put that value in `config.py`.

**5. Dry-run** (no hardware, prints commands) then the real run:
```
python -m aimplotter.velocity_main --no-serial
python -m aimplotter.velocity_main
```
Kill switch: **`q`** (global). Teardown zeroes velocity and releases the servo.

**Tuning** (all in `config.py`, no reflash): `kp_v` = chase strength (raise for faster, lower if it overshoots), `max_speed_mm_s` = speed cap, `vel_deadzone_tol_px` = how tightly it centers before clicking. `kff` (feedforward) is off by default — at high frame rates it amplifies detection noise.

## _Bill of Materials_
I will be buying the few materials I need out of pocket, however these are the required components to reproduce.

| Item Name | Quantity | Price (Est. USD) | Link to Buy |
| :--- | :---: | :---: | :--- |
| **MGN12H Linear Guide Rails (300mm length with carriage block)** | 3 | $60.00 ($20.00 each) | [Amazon](https://www.amazon.com/s?k=MGN12H+300mm+linear+rail) / [AliExpress](https://www.aliexpress.com/w/wholesale-MGN12H-300mm.html) |
| **Arduino Uno R3 + CNC Shield V3 + A4988/TMC2208 Driver Bundle** | 1 | $22.00 | [Amazon](https://www.amazon.com/s?k=Arduino+Uno+CNC+Shield+V3+bundle) / [AliExpress](https://www.aliexpress.com/w/wholesale-Arduino+Uno+CNC+Shield+bundle.html) |
| **NEMA 17 Stepper Motor (1.5A - 2.0A)** | 2 | $24.00 ($12.00 each) | [Amazon](https://www.amazon.com/s?k=NEMA+17+stepper+motor) / [Adafruit](https://www.adafruit.com/product/324) |
| **SG90 Micro Servo Motor** | 1 | $4.00 | [Amazon](https://www.amazon.com/s?k=SG90+micro+servo) / [Adafruit](https://www.adafruit.com/product/169) |
| **12V 3A DC Power Supply Adapter** | 1 | $10.00 | [Amazon](https://www.amazon.com/s?k=12v+3a+power+supply+barrel+jack) |
| **GT2 Timing Belt (6mm wide, 2-3 meters)** | 1 | $8.00 | [Amazon](https://www.amazon.com/s?k=GT2+timing+belt+6mm) |
| **GT2 20-Tooth Drive Pulleys (5mm bore)** | 2 | $5.00 ($2.50 each) | [Amazon](https://www.amazon.com/s?k=GT2+20T+pulley+5mm+bore) |
| **GT2 Idler Pulleys (with bearings)** | 2 | $4.00 ($2.00 each) | [Amazon](https://www.amazon.com/s?k=GT2+idler+pulley) |
| **PETG 3D Printer Filament (1kg Spool)** | 1 | $20.00 | [Amazon](https://www.amazon.com/s?k=PETG+filament+1kg) |
| **M3 & M5 Machine Screws and Nuts Assortment Box** | 1 | $13.00 | [Amazon](https://www.amazon.com/s?k=M3+M5+screw+assortment) |
| **Jumper Wires (Female-to-Female)** | 1 | $5.00 | [Amazon](https://www.amazon.com/s?k=female+to+female+jumper+wires) |
| **USB Type-A to Type-B Printer Cable** | 1 | $6.00 | [Amazon](https://www.amazon.com/s?k=usb+a+to+b+cable) |
| **ESTIMATED TOTAL PRICE** | **-** | **$181.00** | **-** |

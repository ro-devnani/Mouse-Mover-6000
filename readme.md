# _Mouse Mover 6000_
An XY plotter based system that can control the movement and clicks of your computer mouse in order to *help* one play shooter based video games by assisting aim.

## _Image Gallery_
<img width="1119" height="665" alt="mm6 image 1" src="https://github.com/user-attachments/assets/918a0417-caf0-4016-a666-a7f2a608fe40" />
<img width="879" height="355" alt="mm6 image 2" src="https://github.com/user-attachments/assets/968aeb85-c7f1-4e76-987c-5b29a6f8b62d" />
<img width="946" height="388" alt="mm6 image 3" src="https://github.com/user-attachments/assets/b5b2995f-b22c-4685-99d8-a65c99ffaaf2" />
<img width="875" height="770" alt="mm6 image 4" src="https://github.com/user-attachments/assets/f58645ee-d676-4509-a19c-8337f3116ffb" />
<img width="875" height="770" alt="mm6 image 4" src="https://github.com/user-attachments/assets/3c49b6f9-93ed-43ec-ab85-87196cc17160" />
<img width="1920" height="1079" alt="mm6 detection code" src="https://github.com/user-attachments/assets/5fe688be-93d7-4a38-ae77-853f87bf1b5f" />


## _How it Works_
By using a color detection model that takes screenshots of the users page, the algorithm can successfully find the targets that will be need to shot at and find the closest one. Then, the location is compared to the current mouse position and the distance/path to the next target is determined. That is then converted into gcode which is sent through USB to the Arduino Uno with a CNC Shield V3 running GRBL.

This then controls the two Nema17 stepper motors to move in order to turn the belts a certain distance and with it move the mouse to the correct location. Once on the target, the SG90 servo rotates in order to click the mouse button, after which the process repeats again for the next closest target.

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

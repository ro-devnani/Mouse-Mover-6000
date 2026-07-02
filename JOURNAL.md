# **Initial Research + Starting CAD**
**Hours Spent: 0.5**
**Date(s): 6/23/26**
The idea starts with creating my own xy plotter of sorts, however I am still deciding on how large I wanted to make it so I only made the edge that the rail slots into so far. 

While CAD-ing, I was looking at other opensource designs as well as researching the exact model of rail/pulley system I wanted to use and decided on the MGN12H 300mm and GT2 pulleys and belts. 

Next will most likely be adding the model of the rail and building the "x direction" pulley system.
![](https://stardance.hackclub.com/rails/active_storage/representations/proxy/eyJfcmFpbHMiOnsiZGF0YSI6NzQyMTIsInB1ciI6ImJsb2JfaWQifX0=--55835bab102a97427402d6f43c4524647c80c5ba/eyJfcmFpbHMiOnsiZGF0YSI6eyJmb3JtYXQiOiJ3ZWJwIiwicmVzaXplX3RvX2xpbWl0IjpbMTYwMCw5MDBdLCJzYXZlciI6eyJzdHJpcCI6dHJ1ZSwicXVhbGl0eSI6NzV9fSwicHVyIjoidmFyaWF0aW9uIn19--3bc8a2c9d65e3b087c0c0b37dcfb642bb247bc73/a6822f88-9faf-4fdc-9745-20acaf254915.png)

# **Finish Edge and Start Central Plate**
**Hours Spent: 0.75**
**Date(s): 6/23/26**

It took a while to find some proper dimensions for the holes, partially because I was looking at the wrong linear rail, but I added the last part which was the screw hole to the edge which may or may not be adjusted.

Then, I began the central plate which the motors for both the x and y axes will be on. This means 2 sets of mounts for each of the stepper motors and another for the the “y axis” rail, and one more to mount onto the x axis block, all using m3 screws.

On top of that, I added m5 screw holes that will be for the idler gears of the x axis.

With two of the technically most complex parts finished, the next part should be the y axis block mount alongside the mouse clicker. I also lowk need to add mounts for the limit switches, but i lowk dont want to, maybe ill just glue em on.
![](https://stardance.hackclub.com/rails/active_storage/representations/proxy/eyJfcmFpbHMiOnsiZGF0YSI6NzQzNDAsInB1ciI6ImJsb2JfaWQifX0=--23cc139f7c451f726a232606ada5f3be19dc56b9/eyJfcmFpbHMiOnsiZGF0YSI6eyJmb3JtYXQiOiJ3ZWJwIiwicmVzaXplX3RvX2xpbWl0IjpbMTYwMCw5MDBdLCJzYXZlciI6eyJzdHJpcCI6dHJ1ZSwicXVhbGl0eSI6NzV9fSwicHVyIjoidmFyaWF0aW9uIn19--3bc8a2c9d65e3b087c0c0b37dcfb642bb247bc73/image.png)

# **Begin Final Assembly**
**Hours Spent: 3.75**
**Date(s): 6/27/26**

With some of the custom designed parts finished, I began to work on the final assembly for the CAD that combined my parts with some external models of the parts I planned to use.

I had lost around an hour and an half of work due to Lookout crashing without me knowing, but most of it was redone in order to create the 300mm rail with only the model of the 100mm rail online after the first one failed.

I put the rail on both edge pieces (including remaking one because I realized they were not symmetrical), added the central plate to the x axis block, added the stepper motors, added the G2 pulleys and idler pulleys for both axes, added the y axis rail, and made and added the idler pulley for the y axis. I also added the required screws and nuts.

This also includes many smaller changes such as struggling and adjusting the screw positions, changing distances of screw holes on the central plate, changing the mount side of the y axis stepper motor, and many other small size revisions.

To Do List:
-   Create the Y axis mount
-   Add the belts
-   Add a rail parallel to the x axis for better stability
-   Add a mount for the Arduino Uno
-   Create the wiring diagram
-   Code

I’ll hopefully update this list through the final logs over the next few days.

![](https://stardance.hackclub.com/rails/active_storage/representations/proxy/eyJfcmFpbHMiOnsiZGF0YSI6ODU5NDQsInB1ciI6ImJsb2JfaWQifX0=--07db731d4d635ac21719840f1917e7e5a8ff37b4/eyJfcmFpbHMiOnsiZGF0YSI6eyJmb3JtYXQiOiJ3ZWJwIiwicmVzaXplX3RvX2xpbWl0IjpbMTYwMCw5MDBdLCJzYXZlciI6eyJzdHJpcCI6dHJ1ZSwicXVhbGl0eSI6NzV9fSwicHVyIjoidmFyaWF0aW9uIn19--3bc8a2c9d65e3b087c0c0b37dcfb642bb247bc73/image.png)
![](https://stardance.hackclub.com/rails/active_storage/representations/proxy/eyJfcmFpbHMiOnsiZGF0YSI6ODU5NDUsInB1ciI6ImJsb2JfaWQifX0=--24ebdda760510a8a4395aa7a6bf7a604ddc4c76c/eyJfcmFpbHMiOnsiZGF0YSI6eyJmb3JtYXQiOiJ3ZWJwIiwicmVzaXplX3RvX2xpbWl0IjpbMTYwMCw5MDBdLCJzYXZlciI6eyJzdHJpcCI6dHJ1ZSwicXVhbGl0eSI6NzV9fSwicHVyIjoidmFyaWF0aW9uIn19--3bc8a2c9d65e3b087c0c0b37dcfb642bb247bc73/image.png)

# _Quick Fixes + Parallel Rail_
**Hours Spent: 0.75**
**Date(s): 6/28/26**

Made some quick fixes in positioning of the outlets for the stepper motors.

Then began working on the parallel rail for the x axis. I had to delete the previous end piece for the y axis to do so. It had a few problems in alignment of the 2 pulleys, but it should be accurate now.

To Do List:
-   Create the Y axis mount
-   Add the belts
-   ~~Add a rail parallel to the x axis for better stability~~
-   (New) Remake the edge pieces so it connects to a proper square mount for stability
-   Add a mount for the Arduino Uno
-   Create the wiring diagram
-   Code
![](https://stardance.hackclub.com/rails/active_storage/representations/proxy/eyJfcmFpbHMiOnsiZGF0YSI6ODg5NzAsInB1ciI6ImJsb2JfaWQifX0=--84ed8c88462f12075a6da7d8fd435fa6f7eaf76f/eyJfcmFpbHMiOnsiZGF0YSI6eyJmb3JtYXQiOiJ3ZWJwIiwicmVzaXplX3RvX2xpbWl0IjpbMTYwMCw5MDBdLCJzYXZlciI6eyJzdHJpcCI6dHJ1ZSwicXVhbGl0eSI6NzV9fSwicHVyIjoidmFyaWF0aW9uIn19--3bc8a2c9d65e3b087c0c0b37dcfb642bb247bc73/image.png)

# _Begin Working on & Finish Code (For Now)_
**Hours Spent: 3**
**Date(s): 6/29/26**

After working on the CAD for so long, I decided to begin working on the actual object detection and gcode generation portion that will be running this build. 

Currently, all I am training this for is to work in AimLabs, as it is very easy to create a model to aim at targets because of their distinctive neon blue hue as it only needs to detect colors and not full objects. After taking pre-existing detection projects and tweaking them to my use case, I had a passable detection that worked in AimLabs and could detect the correct blue color/target and the closest one. 

For the gcode, that would go into GRBL that will run on the Arduino Uno with a CNC Shield V3, I had to similarly take some inspiration from the internet. Because the very crucial information of mm per step was missing, which I cannot reliably obtain until the build is finished, I had to leave the code very generic for the time being, which means I will need to update it after building.

Claude Code was used to help bug fix and make sure I was not going insane.

To Do List:
-   Create the Y axis mount
-   Add the belts
-   Remake the edge pieces so it connects to a proper square mount for stability
-   Add a mount for the Arduino Uno
-   Create the wiring diagram
-   ~~Code~~
<img width="1920" height="1079" alt="mm6 detection code" src="https://github.com/user-attachments/assets/3f3f861c-14b2-4f7d-ba7d-5f0cf006244a" />

# _Finish CAD_
**Hours Spent: 5.5**
**Date(s): 6/30/26 - 7/1/26**

With the CAD being my largest obstacle to be completed with the design, I decided to complete it all.

First, I made the Y Axis Mount that would be holding the mouse itself to move alongside the plotter. The actual holder for the mouse was very simple, taking my mouse (the Razer Deathadder Essential) as the reference, I added a small box that would hold the mouse with less than 1 mm tolerance of extra space. This keeps the mechanical failure risk to a minimum while also being very efficient for the simple task. I also decided to add a SG90 servo onto the bottom of the mount that would be clicking the left click button.

Next, I decided to remake the mounts for the linear rails as they were very inefficient after adding the parallel x rail. Following research from several other plotter/xy designs, I made rectangular mounts with a threaded rod between them in order to secure the entire build together. I also added 2 triangular mounts to each side which I will add rubber feet to as well to prevent shaking from the plotter movement. I also made them thicker than in the previous designs.

Then, I added belts to the X and Y axes. The Y axis was simple after a bit of error with the placement of the idler pulley. However, the X axis was a bit trickier. Because I had to snake the belt between 2 idler pulleys, but I added it eventually which took me a bit longer. 

For the Arduino mount, I realized the most difficult part of the location would be the wiring to the servo, but even that was pretty trivial so the location was not an issue. For ease of use and removal, I just put it in a box on one of the ends.

The reason this section took a lot longer than the rest was the constant smaller problems I ran into and a lot of prototyping and deciding how/why I wanted to place an object and then actually doing it for several prototypes.

To Do List:
-   ~~Create the Y axis mount~~
-   ~~Add the belts~~
-   ~~Remake the edge pieces so it connects to a proper square mount for stability~~
-   ~~Add a mount for the Arduino Uno~~
-   Create the wiring diagram
-   (New) Create Journal and readme
<img width="1119" height="665" alt="mm6 image 1" src="https://github.com/user-attachments/assets/dab3b46b-e59f-4a26-8aad-63ea5061d8bc" />

# _Final Touches_
**Hours Spent: 1.25**
**Date(s): 7/1/26 - 7/2/26**

With the CAD done, I just began to prep and create my repo before I submit. 

The electrical diagram was very simple, and I made it in MS paint because the different softwares I tried were very annoying. Because there are not too many components though, I believe it turned out alright.

The journal and readme files took the longest because they were hand-typed (no ai). Lookout conked on me 2 times so I gave up on it, but I could still copy around half the work from the Stardance project. 

# _Overall_
**Time Spent: 15.5 hours** 

### LinuxCNC cheap MPG with Novusun NVMPG RJ45 
#### LCD and button communication uses USB Serial adapter
#### Encoder input uses MESA 7i77

### What works?
- Jogging with 100 count per rev encoder
- Encoder resolution mulitplier buttons (x1/x10/x100/x1000)
- Axis selection buttons (x,y,x,all)
- ZERO - Zero selected axis button
- SPINDLE - Spindle toggle button
- LEFT/RIGHT side buttons - ESTOP
- HOME - Re-Homing selected axis
- LCD Displays
  - Selected axis
  - X Y Z coordinates
  - Spindle RPM
  - Spindle on/off status
  - Feed override (FRO%)

### Needs more work
- Touching any button or the encoder during homing results in eStop
- Selected axis not reflected in AXIS UI
- Zeroing an axis does not cause AXIS UI to refresh.

### Tested with..
LINUXCNC - 2.10.0-pre0-997-g1c1f6feb6
Kernel - Linux 4.19.0-23-rt-amd64 #1 SMP PREEMPT RT Debian 4.19.269-1 (2022-12-20) x86_64 GNU/Linux

### My Hardware
#### CPU
AAEON UP-CHT01/UP-CHT01, BIOS UPC1DM25 06/25/2021
Intel(R) Atom(TM) x5-Z8350  CPU @ 1.44GHz
2GB Memory, 4GB eMMC

#### I/O
Mesa 7i92T, 7i77, 7i76

#### Drives
- X,Y Servos; Mitsubishi MR-J3-40A
- Z Stepper DM556T



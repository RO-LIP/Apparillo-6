#!/usr/bin/python3
from gpiozero import RGBLED, Button, LED, DigitalOutputDevice
from time import sleep
from subprocess import getoutput
from signal import pause
from os import system

'''
Script zum aktivieren verschiedener Ein- und Ausgabegeraete
-Rotary Encoder zur Lautstaerkeregelung
-RGB LED zur Anzeige/Visualisierung des Lautstaerkepegels
-Taster zum Pausieren der Wiedergabe und Herunterfahren des Pi
-Schalter/Taster und Relais zum abschalten des LCD
-Timer zum Abschalten des LCD
-Startup Lautstaerke
-UVLO selbsthaltung

Relays sollten über Transistor angesteuert werden:
https://www.elektronik-kompendium.de/public/schaerer/powsw3.htmhttps://www.elektronik-kompendium.de/public/schaerer/powsw3.htm
'''


'''
Einstellungen in diesem Script: 

Pins und Betriebssystem(os) muss eingestellt werden. 
Befehle werden dann automatisch angepasst.
Bei moOde muss Rotary Encoder ueber WebUI aktiviert werden (Standartpins 4,5(GPIO23,24))


Einstellungen an Pi:

Prinzipielle Einstellungen:
Service in systemd für dieses Script einrichten
Kontrollieren ob in /boot/config.txt folgende Parameter gesetzt sind:
disable_splash=1
hdmi_drive=2
dtparam=audio=off
max_usb_current=1

UVLO: 
Das Relay zum Halten der Verbindung LiPo-UVLO wird über einen Transistor (GPIO9) angesteuert. 
Die Einstellung dazu muss in /boot/config.txt hinzugefuegt werden: 
dtoverlay=gpio-poweroff,gpiopin=9,active_low

LCD:
Das Relay zum Ein-/Ausschalten des Touchscreens wird über einen Transistor (GPIO11) angesteuert.
Einstellungen fuer 5Inch 15:9 Touch Display. Am Display selbst sollte 16:9 eingestellt werden 
Der Touchscreen wird in /boot/config.txt konfiguriert:
hdmi_force_hotplug=1
hdmi_group=2
hdmi_mode=87
config_hdmi_boost=7
hdmi_cvt 800 480 60 6
display_hdmi_rotate=1
Touch eingabe wird in /etc/X11/xorg.conf.d/40-libinput.conf gedreht mit: 
Option "CalibrationMatrix" "0 1 0 -1 0 1 0 0 1"
'''


#Alle Buttons pulled up ausser rotary button

os = "moode"
#os="volumio" '''alle volumio befehle muessen noch getestet werden'''


'''
Festlegen der Pins fuer die angeschlossenen I/O
GPIO22,23,24 werden normalerweise fuer Rotary verwendet
Diese GPIOs nicht verwenden: 
GPIO0,GPIO1
GPIO0,1,26 sind nicht auf Proto HAT.
GPIO2,3,18,19,20,21 werden von I2C/JustboomAmp/HifiberryDAC/HifiberryAMP2 verwendet
GPIO2,3,18,19,20,21,4 wird von HifiberryAMP2 verwendet

'''

laser_BTN_P = 7         #Taster um LCD ein und aus zu schalten
laser_LED_P = 8
missile_BTN_P = None    #Nicht an GPIO angeschlossen. Schaltet Apparillo ein
missile_LED_P = None    #Wird evtl nicht an GPIO angeschlossen sondern an UVLO
lcd_RELAY_P = 11 #sclk  #Relay+Transistor zum einschalten des LCDs; Bildschirm ist an wenn Pin high
lcd_time = 600          #Zeit in Sekunden nach denen der LCD automatisch ausgeschaltet wird.
uvlo_relay = 9   #miso  #Relay+Transistor zum Unterbrechen der Messung des UVLO; eingestellt in /boot/config
rot_clk_P = 23          #Pins des Rotary Encoders; Mittlerer Pin auf GND
rot_data_P = 24         #Vertausche CLK und Data um Drehrichtung zu aendern
rot_BTN_P = 22          #pulled down button zum pausieren und herunterfahren des pi
rot_RGB_P_red = 14      #RGB LED zum visualisiern des Lautstaerkepegels
rot_RGB_P_green = 27
rot_RGB_P_blue = 17     #Die blaue Led wird noch nicht bzw. fuer nix wichtiges verwendet
vol_red = 80            #Lautstaerke ab der die LED rot leuchtet
vol_green = 40          #Lautstaerke ab der die LED rot leuchtet
holdtime = 5            #Dauer bis jeweiliger Taster als gehalten erkannt wird







def volume(arg=""): #Kann mit leer, integer oder "up <step>" "dn <step>" aufgerufen werden, dann als string (in "") damit als 1 argument erkannt wird
    arg = str(arg)
    if os == "moode":
        getoutput("/var/www/vol.sh " + arg)
        try:
            return(int(getoutput("/var/www/vol.sh")))
        except ValueError:
            return(1000)
    elif os == "volumio":
        getoutput("volumio volume " + arg)


def vol_color(): #Bestimmt die Farbe der LED passend zur Lautstaerke und stellt die LED ein
    vol = volume()
    if vol == 1000:
        newcol = rot_RGB.color
    elif vol <= vol_green:
        newcol = (0, 1, 0)
    elif vol >= vol_red:
        newcol = (1, 0, 0)
    elif vol <= vol_mid:
        r = ((vol - vol_green)/(vol_mid - vol_green))
        newcol = (r, 1, 0)
    else:
        g = ((vol - vol_mid)/(vol_red -vol_mid))
        newcol = (1, 1-g, 0)
    rot_RGB.pulse(fade_in_time=0, fade_out_time=0.1, on_color=rot_RGB.color, off_color=newcol, n=1, background=True) #Led fade von altem zu neuem wert


def toggle(): #Wechselt zwischen play und pause
    if os == "moode":
        print("ich toggle")
        getoutput("mpc toggle")
    elif os == "volumio":
        getoutput("volumio toggle")

def rotation(): #Aendert Lautstaerke bei Rotation. Nur bei Volumio noetig
    rot_data.when_pressed = upvolume
    rot_data.when_released = downvolume

def upvolume():
    rot_data.when_pressed = None
    rot_data.when_released = None
    volume("plus")

def downvolume():
    rot_data.when_pressed = None
    rot_data.when_released = None
    volume("minus")

def held(): #Wenn der BTN des Rotarys gehalten wird, wird der Raspy heruntergefahren
    #print("bitte lass nicht los damit ich nicht herunterfahre")
    rot_RGB.blink(on_time=0.5,off_time=0.5,on_color=(0,0,1),off_color=(1,0,0),n=6,background=False)
    if rot_BTN.is_held: #Wenn der BTN weiter gehalten wird, wird der vorgang abgebriochen und alles geht weiter wie vorher
        #print("danke")
        rot_RGB.blink(on_time=0.5,off_time=0.5,on_color=(0,0,1),off_color=(0,1,0),n=2,background=False)
    else:
        shutdown()

def shutdown():
    print("Ich wuerde jetzt abschalten! poweroff!")
    system("poweroff")

def toggle_lcd(): #Schaltet Relay fuer Bildschirm ein und aus
    if lcd_RELAY.value == True:
        laser_LED.off()
        lcd_RELAY.off()
    elif lcd_RELAY.value == False:
        laser_LED.blink(on_time=lcd_time,off_time=None, n=1, background=True)
        lcd_RELAY.blink(on_time=lcd_time, off_time=None, n=1, background=True)
    laser_BTN.wait_for_release(timeout=0.2)



try:
    laser_BTN = Button(laser_BTN_P, pull_up=True, bounce_time=None, hold_time=holdtime, hold_repeat=True)
    laser_LED = LED(laser_LED_P, active_high=True, initial_value=False)
    rot_BTN = Button(rot_BTN_P, pull_up=False, bounce_time=None, hold_time=holdtime, hold_repeat=False)
    rot_RGB = RGBLED(rot_RGB_P_red, rot_RGB_P_green, rot_RGB_P_blue, active_high=False, initial_value=(0,0,0))
#   missile_LED = LED(missile_LED_P, active_high=True, initial_value=True)

    lcd_RELAY = DigitalOutputDevice(lcd_RELAY_P, initial_value=False)
    vol_mid = vol_green + (vol_red - vol_green)/2

    if os == "moode": #Setzten einer Start-Lautstaerke
        startupvol = str(20)
        getoutput("/var/www/vol.sh " + startupvol)

    #Laesst die Rotary LED aufleuchten/blinken um einen Abgeschlossenen Startvorgang zu signalisieren
    rot_RGB.blink(on_time=1, off_time=0.3, fade_in_time=0.0, fade_out_time=0.2, on_color=(0, 0, 0), off_color=(1, 0, 0), n=1, background=False)
    rot_RGB.blink(on_time=0.3, off_time=0.3, fade_in_time=0.2, fade_out_time=0.2, on_color=(0, 1, 1), off_color=(1, 0, 1), n=1, background=False)
    rot_RGB.blink(on_time=0.3, off_time=0.3, fade_in_time=0.2, fade_out_time=0.2, on_color=(1, 1, 0), off_color=(0, 0, 1), n=1, background=False)
    rot_RGB.blink(on_time=0.3, off_time=0.3, fade_in_time=0.2, fade_out_time=0.2, on_color=(1, 1, 1), off_color=(0, 1, 0), n=1, background=False)

    rot_BTN.when_pressed = toggle
    rot_BTN.when_held = held
    laser_BTN.when_pressed = toggle_lcd

    if os == "volumio":
        rot_clk = Button(rot_clk_P, pull_up=True)
        rot_data = Button(rot_data_P, pull_up=True, hold_repeat=True)
        rot_clk.when_pressed = rotation  # muss bei volumio wieder aktiviert werden

    while True:
        rot_BTN.wait_for_release()
        vol_color()
        sleep(0.2)

finally:
    print("fertig")

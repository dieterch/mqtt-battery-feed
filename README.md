# mqtt-battery-feed
feeds voltage & temperature data collected by a shelly UNI device to 
https://github.com/mr-manuel/venus-os_dbus-mqtt-battery/tree/master/dbus-mqtt-battery

# installation

1. Copy the `mqtt-battery-feed` folder to `/data/etc` on your Venus OS device

2. Run `bash /data/etc/mqtt-battery-feed/install.sh` as root

   The daemon-tools should start this service automatically within seconds.

### Uninstall

Run `/data/etc/mqtt-battery-feed/uninstall.sh`

### Restart

Run `/data/etc/mqtt-battery-feed/restart.sh`

### Debugging

The logs can be checked with `tail -n 100 -f /data/log/mqtt-battery-feed/current | tai64nlocal`

The service status can be checked with svstat `svstat /service/mqtt-battery-feed`

This will output somethink like `/service/mqtt-battery-feed: up (pid 5845) 185 seconds`


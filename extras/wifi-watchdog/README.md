# Optional: Wi-Fi reconnect watchdog

When the robot drops Wi-Fi and joins another network (home Wi-Fi to a phone hotspot, for example), the conversation session can be left connected to nothing. This service watches the system journal for reconnect events, refreshes memories, restarts the app, and checks that your profile loaded.

Install on the robot:

```bash
sudo cp ~/reachy-aiden/extras/wifi-watchdog/wifi-reconnect-watchdog.sh /home/pollen/companion/
sudo chmod +x /home/pollen/companion/wifi-reconnect-watchdog.sh
sudo cp ~/reachy-aiden/extras/wifi-watchdog/wifi-reconnect-watchdog.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now wifi-reconnect-watchdog.service
```

To give the robot more than one network, save each one and set priorities so it prefers home and falls back to the hotspot:

```bash
sudo nmcli device wifi connect "HomeNetwork" password "home-password"
sudo nmcli device wifi connect "PhoneHotspot" password "hotspot-password"
sudo nmcli connection modify "HomeNetwork" connection.autoconnect-priority 100
sudo nmcli connection modify "PhoneHotspot" connection.autoconnect-priority 50
```

On phone hotspots, `reachy-mini.local` often fails to resolve. Use the robot's IP address from the hotspot's connected-devices list instead.

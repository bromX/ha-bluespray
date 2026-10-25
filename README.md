<p align="center">
  <img src="https://raw.githubusercontent.com/bromX/ha-bluespray/main/images/icon.png" width="128" alt="BlueSpray">
</p>

# BlueSpray for Home Assistant

Created using Claude using the BlueSpray local API.
Only works with a local controller directly accessing it via the rest API.

This is currently a read only integration polling data from the controller.
Provides details on the irrigation systems operation and upcoming events.
In the future I might rebuild this to be read-write.

I have not tested flow or forecast sensors as I don't have either enabled on my system.

Install: copy `custom_components/bluespray` into your HA config's `custom_components/` folder,
restart HA, then Settings > Devices & services > Add integration > "BlueSpray".
or use HACS

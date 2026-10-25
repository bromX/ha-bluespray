<p align="center">
  <img src="https://raw.githubusercontent.com/bromX/ha-bluespray/main/images/icon.png" width="128" alt="BlueSpray">
</p>

# BlueSpray for Home Assistant (read-only)

Comments: Created using Claude using the Blyespray local API.
Only works with a local controller directly accessing it via the rest API.

This is currently a read only integration polling data from the controller every 30 second.
In the future I might rebuild this to be read-write.


Install: copy `custom_components/bluespray` into your HA config's `custom_components/` folder,
restart HA, then Settings > Devices & services > Add integration > "BlueSpray".

Debug logging (configuration.yaml):

    logger:
      logs:
        custom_components.bluespray: debug

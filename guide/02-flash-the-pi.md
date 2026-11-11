# 2. Flash the Pi

[◀ What you need](01-what-you-need.md) · Next: [Wire the float switch ▶](03-wire-it-up.md)

We don't need a desktop, so we use **Raspberry Pi OS Lite (64-bit)**: no GUI, small, fast.

1. Install the latest [Raspberry Pi Imager](https://www.raspberrypi.com/software/) on your computer and put the microSD card in.
2. **Device:** your Pi model.
3. **OS:** Raspberry Pi OS (other) → **Raspberry Pi OS Lite (64-bit)**.
4. **Storage:** your microSD card.
5. **Customisation:** Imager walks you through a few pages. Fill them in:
   - **Hostname:** something like `pi-toilet`.
   - **User:** a username and password.
   - **Wi-Fi:** your network name and password (skip it if you'll plug in Ethernet).
   - **Remote access:** turn on **Enable SSH**.
6. Write the card.

> Older versions of Imager hide these under **Edit Settings**, with SSH on the **Services** tab. Same settings, different screen.

> Don't plug the Pi in yet. We wire the float switch first, with the power off.

When you do boot it later, connect from your computer with:

```bash
ssh <your-username>@pi-toilet.local
```

If `.local` names don't work on your network, find the Pi's IP address in your router's client list and use that.

💡 **Give it a fixed IP.** Set a DHCP reservation for the Pi in your router, so your toilet always has the same IP address. Mine is on my network next to everything else. As it should be.

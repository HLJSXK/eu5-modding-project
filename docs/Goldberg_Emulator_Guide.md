# Goldberg Emulator for EU5 LAN Multiplayer

This folder contains the Goldberg Steam Emulator configuration for European Universalis 5 LAN multiplayer.

## 📁 Folder Structure

```
goldberg_emulator/
├── steam_api64.dll          # Goldberg Steam Emulator DLL
├── steam_settings/          # Configuration folder
│   ├── DLC.txt             # DLC configuration file
│   └── mods/               # Mods folder for LAN sessions
└── README.md               # This file
```

## 🎯 Purpose

The Goldberg Steam Emulator allows EU5 to run in LAN mode without requiring Steam authentication. This enables:

- **Local network multiplayer** without internet connection
- **Virtual LAN (VPN)** multiplayer using tools like n2n
- **Private game sessions** with friends

## 🔧 Configuration Files

### Account Name and Steam ID

The emulator allows you to configure your account name and Steam ID that will be displayed in LAN multiplayer sessions.

**Configuration Files:**
- `steam_settings/force_account_name.txt` - Your display name in multiplayer
- `steam_settings/force_steamid.txt` - Your unique Steam ID (17 digits)

**Using the deployment tool:**
```bash
# Deploy with custom account name and Steam ID
eu5-deployer.exe --account-name "YourName" --steam-id "76561198012345678"

# Deploy with default values (EU5Player / 76561197960287930)
eu5-deployer.exe
```

**Manual configuration:**
1. Navigate to `<EU5_Installation>/binaries/steam_settings/`
2. Edit `force_account_name.txt` - Enter your desired display name
3. Edit `force_steamid.txt` - Enter a valid 17-digit Steam ID starting with `7656119`

**Steam ID Format:**
- Must be exactly 17 digits
- Must start with `7656119`
- Example: `76561197960287930`

**Important:** All players in a LAN session should use **different Steam IDs** to avoid conflicts. You can generate unique IDs by incrementing the last digits (e.g., `76561197960287931`, `76561197960287932`, etc.).

### steam_api64.dll

This is the Goldberg Steam Emulator DLL that replaces the original Steam API DLL in the EU5 binaries folder. It intercepts Steam API calls and provides LAN networking functionality.

**Source:** [Goldberg Steam Emulator](https://gitlab.com/Mr_Goldberg/goldberg_emulator)

### steam_settings/DLC.txt

This file lists the DLC IDs that should be enabled for all players in the LAN session. 

**Format:**
- One DLC ID per line
- Lines starting with `#` are comments
- Empty lines are ignored

**Example:**
```
# EU5 DLC Configuration
2883680
2883681
```

**Note:** You need to add the actual DLC IDs for EU5. You can find these by:
1. Checking Steam's app manifest files
2. Using SteamDB (https://steamdb.info/)
3. Looking at the game's DLC page on Steam

### steam_settings/mods/

This folder contains mod configurations that will be available during LAN sessions. Place mod folders here that you want to use in multiplayer.

**Important:** All players must have the same mods for compatibility!

## 🚀 Deployment

### Automatic Deployment

Use the provided deployment script:

```bash
# Auto-detect EU5 installation and deploy
python3 tools/deploy_goldberg.py

# Specify EU5 path manually
python3 tools/deploy_goldberg.py --eu5-path "/path/to/Europa Universalis V"

# Restore original files
python3 tools/deploy_goldberg.py --restore
```

### Manual Deployment

If you prefer to deploy manually:

1. **Backup original files:**
   ```bash
   cd "<EU5_Installation>/binaries"
   mkdir .goldberg_backup
   cp steam_api64.dll .goldberg_backup/steam_api64.dll.original
   ```

2. **Copy Goldberg DLL:**
   ```bash
   cp goldberg_emulator/steam_api64.dll "<EU5_Installation>/binaries/"
   ```

3. **Copy steam_settings folder:**
   ```bash
   cp -r goldberg_emulator/steam_settings "<EU5_Installation>/binaries/"
   ```

4. **Launch EU5** - The game will now run in LAN mode

### Restoration

To restore original Steam functionality:

```bash
# Using script
python3 tools/deploy_goldberg.py --restore

# Or manually
cd "<EU5_Installation>/binaries"
cp .goldberg_backup/steam_api64.dll.original steam_api64.dll
rm -rf steam_settings
```

## 🌐 Network Setup

### Local LAN

If all players are on the same physical network, no additional setup is needed. Just:
1. Deploy Goldberg Emulator on all machines
2. Launch EU5
3. One player hosts, others join via LAN

### Virtual LAN (VPN)

For remote play, use a VPN solution to create a virtual LAN:

**Recommended tools:**
- **n2n** - Peer-to-peer VPN (recommended for this project)
- **ZeroTier** - Easy-to-use virtual network
- **Hamachi** - Popular but proprietary
- **Tailscale** - Modern WireGuard-based VPN

For n2n setup, refer to: https://github.com/ntop/n2n

## ⚠️ Important Notes

1. **Backup First:** Always backup your original `steam_api64.dll` before replacing it
2. **Antivirus:** Some antivirus software may flag Goldberg Emulator as suspicious. Add an exception if needed
3. **Updates:** After EU5 updates, you may need to restore the original DLL first, then re-deploy Goldberg
4. **Compatibility:** All players must use the same version of EU5 and have the same DLCs/mods enabled
5. **Legal:** This is for LAN play only. All players should own legitimate copies of EU5

## 📚 References

- [Goldberg Steam Emulator](https://gitlab.com/Mr_Goldberg/goldberg_emulator) - Official project
- [Goldberg Documentation](https://gitlab.com/Mr_Goldberg/goldberg_emulator/-/blob/master/README.md) - Configuration guide
- [n2n VPN](https://github.com/ntop/n2n) - Peer-to-peer VPN for virtual LAN

## 🐛 Troubleshooting

### Game won't start
- Restore original `steam_api64.dll` and verify game files in Steam
- Make sure you're using the correct version of Goldberg for 64-bit

### Can't see other players
- Verify all players are on the same network (physical or virtual)
- Check firewall settings - EU5 needs to be allowed
- Ensure all players have deployed Goldberg Emulator

### DLC not working
- Check that DLC IDs in `DLC.txt` are correct
- Verify the file is in the correct location: `<EU5_Installation>/binaries/steam_settings/DLC.txt`

### Mods not loading
- Ensure mods are in `steam_settings/mods/` folder
- Verify all players have the same mods
- Check mod compatibility with current EU5 version

## 📝 Version History

- **v1.0** (2026-01-22) - Initial setup with folder structure and deployment scripts

---

**Last Updated:** January 22, 2026  
**Maintained by:** EU5 Modding Project Team

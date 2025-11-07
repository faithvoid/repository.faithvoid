# cortanaStats
Background script that automatically fetches Insignia and XLink Kai playercounts, active sessions, upcoming events, and related statistics and displays them on your dashboard if supported by your theme.
Primarily used for cortanaOS, but is built to be skin-agnostic.

## Installation
- Download "cortanaStats" from the repository
- Enable "cortanaStats" in your XBMC Add-On settings, this will automatically run the script on every boot.
- If your theme supports it, everything should Just Work! If it doesn't, read the information below on modifying your theme to support cortanaStats:

## Skin Installation
- Using a text editor of your choice, open the .XML file of the part of the skin you'd like to modify (ie; Home.xml for your skin's home screen)
- Find the label that you'd like to modify (ie; "Games") and modify it according to the following format (note that you may have to use $LOCALIZE[] instead of "Games" if using localized text)
``` <label>Games - $INFO[Skin.String(activeInsigniaSessions)] on Insignia</label> ```
- Reload the skin or restart XBMC4Xbox, and voila! The label you've modified will now be updated every minute.
- For a full list of skin labels, view the "Skin Labels" section below!

## Skin Labels
- onlinePlayers - Combined summary of online players across both Insignia and XLink Kai.
- onlinePlayersHeader - Header-friendly version of combined online player counts.

- onlineInsigniaPlayers - Current number of players online via Insignia.
- onlineXLinkPlayers - Current number of players online via XLink Kai.
- activeInsigniaSessions - Number of active game sessions on Insignia.
- activeXLinkSessions - Number of active game sessions on XLink Kai.
- insigniaSession1-5 - List the names and player counts of currently active games, usually used for <label2>
- xlinkSession1-5 - List the names and player counts of currently active games, usually used for <label2>

- insigniaUsersOnline - Total Insignia users online right now.
- insigniaRegisteredUsers - Total number of users registered on the Insignia service.
- insigniaGamesSupported - Total number of Xbox games currently supported by Insignia.
- insigniaActiveGames - Total number of games currently active (with users) on Insignia.

- xlinkUsersOnline - Number of users currently online on XLink Kai.
- xlinkUsersToday - Total unique user logins today on XLink Kai.
- xlinkServerStatus - Current status of the XLink Kai server.
- xlinkSupportedGames - Number of system-link games supported on XLink Kai.
- xlinkTotalUsers - Total number of registered XLink Kai users.
- xlinkOrbitalServers - Number of orbital servers currently online.
- xlinkOrbitalSync - Sync status of the orbital server mesh.
- xlinkGameTraffic - Rate of game traffic currently being relayed.
- xlinkOrbitalTraffic - Amount of total traffic between orbital servers.

- insigniaEvents - List the next 3 upcoming scheduled game events on Insignia.
- xlinkEvents - List the next 3 upcoming scheduled game events on XLink Kai.



<h1 align="left">
    <a target="_blank">
        Media Cloner
        <img src="http://www.randomnoun.com/wpf/shell32-avi/tshell32_160.gif" width="272" height="60">
    </a>
</h1>


A powerful Telegram forwarding bot with AI captions, custom captions, link remover, replace text system, and advanced forwarding controls.

---

# ✨ Features

- Forward messages, videos, documents, and media
- AI caption formatting
- Custom caption support
- Caption position control
- Link remover
- Replace text system
- Forward with/without forward tag
- Delay & skip system
- User settings system


# ⚙️ Commands

- **`/set_channel`** **`channel_id`** **(Set target channel where files will be forwarded.)**
- **`/set_delay`** **`seconds`** **(Set delay between forwarded messages.)**
- **`/set_skip`** **`number`** **(Skip messages from beginning.)*"
- **`cancel`** **(Stop current forwarding process.)**
- **`/settings`** **(Show current bot settings.)**
- **`/reset_settings`** **(Reset all saved settings.)**
- **`/parse_caption`** **`on/off`** **(Converts messy torrent/file names into clean professional captions.)**
- **`/customised_caption`** **`on/off`** **(Enable or disable custom caption system.)**
- **`/add_caption`** **`text`** **(Add custom caption text.)**
- **`/caption_position`** **`start`** **(Add custom caption before old caption.)**
- **`/caption_position`** **`end`** **(Add custom caption directly at end.)**
- **`/caption_position`** **`end_line`** **(Add custom caption below old caption with blank line.)**
- **`/all_type_link_remove`** **`on/off`** **(Remove all Telegram links, usernames, and URLs.)**
    **Removes:**
      - http links
      - https links
      - t.me links
      - telegram usernames

- **`/replace`** **`old | new`** **(Replace words/text inside captions.)**
- **`/reset_replace`** **(Remove replace settings.)**
- **`/forward_tag`** **`on/off`** **(Enable or disable Telegram forward tag.)**

⚠️ When enabled:
- AI Caption ❌
- Link Remover ❌
- Replace Text ❌
- Custom Caption ❌

will not work because Telegram forwards the original message directly.

---

### 🚀 Start Forwarding

Send:
- Telegram post link (last msg)
- or forward a message to the bot (last post)

Example:

```text
https://t.me/channel/123
```

---
### 🔑 Environment Variables

Create `.env` file:

```env
API_ID=your_api_id
API_HASH=your_api_hash
TG_BOT_TOKEN=your_bot_token
ADMINS=12345,12345
```

---
- Python 3.13+
---

### 📝 Notes

- Settings are temporary
- Settings reset after bot restart
- Bot must be admin in target channel
- Some protected content may not forward

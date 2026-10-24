# Capture coverage

What the Accessibility reader gets from real apps. Measured on 2026-10-25 (macOS 26.6, Apple Silicon) with `make dump BUNDLE=<id>`. No screenshots or OCR fallback, by design (ADR-005): if an app doesn't expose text, we don't capture it.

| App | Bundle ID | Kind | Result | Nodes | Read time | Notes |
|---|---|---|---|---|---|---|
| Google Chrome (Gmail thread) | `com.google.Chrome` | Chromium | ✅ Good | 326 | 55 ms | Reads only the `AXWebArea`. Banner, navigation, search and side-panel landmarks are skipped. About 10 lines of message-toolbar buttons remain |
| Google Chrome (Gmail inbox) | `com.google.Chrome` | Chromium | ✅ Capped | — | — | A long inbox list hits the 20,000-char cap |
| WhatsApp | `net.whatsapp.WhatsApp` | Native | ✅ Good | 88 | 176 ms | Every label carried an invisible U+200E mark, now stripped. The message you're typing is captured |
| Cursor (VS Code fork) | `com.todesktop.230313mzl4w4u92` | Electron | ✅ Capped | 818 | 62 ms | Needs `AXManualAccessibility`. The editor exposes the **whole file** as one value, now cut to the cap |
| Apple Notes | `com.apple.Notes` | Native AppKit | ✅ Good | 634 | 594 ms | Slowest per node: each attribute read is an IPC round trip |
| Slack | `com.tinyspeck.slackmacgap` | Electron | ⏳ Not tested yet | | | Expected to work the same way as Cursor |
| Google Sheets | `com.google.Chrome` | Canvas | ⏳ Not tested yet | | | Cells are drawn on a canvas, so expect little text unless Sheets' screen-reader mode is on |

## Always excluded (never read)

1Password, Bitwarden, LastPass, Keychain Access, Passwords, System Settings, the login window, the screen saver, plus anything you exclude from the menu. Password fields (`AXSecureTextField`) are skipped in every app, and their value is never requested.

## How to add a row

```bash
make dump BUNDLE=com.example.App   # with the app open; prints chars, nodes, timing, a role histogram, and the text
```

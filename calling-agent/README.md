# CallForge Simple Dialer

Very simple calling desk for your 8x8 outreach.

## What it does

1. Import your leads CSV.
2. Shows all business names clearly on the left.
3. Shows the current business name huge and bold.
4. Lets you paste/type your live cold calling script.
5. Sends the current phone number to 8x8.
6. Gives you a fast `End call` button.
7. Lets you mark the result and move to the next lead.

## CSV format

Minimum:

```csv
business,phone
ABC Plumbing,+15551234567
```

Also supported:

- `business`, `company`, or `name`
- `phone`, `phone_number`, `number`, or `tel`
- `notes`
- `outcome`

## Run the app

From this folder:

```powershell
python -m http.server 5178
```

Then open:

```text
http://127.0.0.1:5178/
```

## Install the free 8x8 bridge

This is needed because a normal webpage cannot control another website tab.

1. Open Chrome using your `smeggy` profile.
2. Go to `chrome://extensions`.
3. Turn on `Developer mode`.
4. Click `Load unpacked`.
5. Select this folder:

```text
C:\Users\BST\Downloads\sCRAPER\calling-agent\8x8-bridge
```

6. Open CallForge at `http://127.0.0.1:5178/`.
7. The status should say `8x8 bridge: connected`.

## How calling works

When you press `Call in 8x8`, CallForge sends the number to the Chrome extension.

The extension:

1. Opens or focuses `https://work.8x8.com/calls/all`.
2. Looks for the phone/number input.
3. Pastes the number.
4. Looks for a `Call` or `Dial` button and clicks it.

If the extension is not installed or not connected, the button still opens 8x8 and copies the phone number, so you can paste it manually instead of nothing happening.

When you press `End call`, it looks for an `End`, `Hang up`, or `Hangup` button and clicks it.

## Important limitation

The bridge is best-effort until we test it on your logged-in 8x8 screen. If 8x8 uses unusual labels or hidden controls, the app will still open 8x8, but the input/call/end click may need selector tuning.

After any code update, go to `chrome://extensions` and click the reload icon on `CallForge 8x8 Bridge`.

# Shark Tank Simulator

A static HTML/CSS mockup of a 10-minute investor panel video call interface — think Zoom meets Shark Tank.

## Preview

- **Timer**: Countdown clock (top center)
- **Investor Grid**: 2×3 grid of investor video tiles
- **You Tile**: Founder view with call controls
- **Chat Panel**: Real-time panel messages

## Quick Start

Open directly in your browser:

```bash
open index.html
```

Or run a local server:

```bash
python3 -m http.server 8080
# Visit http://localhost:8080
```

## Investor States

| Investor | Status |
|----------|--------|
| Marcus Kellan | LIVE |
| Victor Slate | LIVE |
| Elena Brooks | OUT |
| Richard Hale | LIVE |
| Daniel Frost | OUT |

Click any investor tile to cycle through states: **LIVE** → **INTERESTED** → **OUT**

## Design Constraints

- No gradients
- No glassmorphism
- No custom fonts (system fonts only)
- Minimal shadows (max `0 1px 2px rgba(0,0,0,0.06)`)
- Clean, restrained, professional aesthetic

## Files

```
├── index.html   # Layout structure
├── styles.css   # Styling
├── app.js       # Tile state cycling (optional)
└── README.md
```

## License

MIT


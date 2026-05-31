# CodeCrafter — The Code Auditor

> *"I've read more Solidity at 3 AM than most devs write in a career. And I do it with a smile."*

## Overview

| Field | Detail |
|-------|--------|
| **Name** | CodeCrafter |
| **Title** | The Code Auditor |
| **Role** | Smart contract quality, code review, security assessment |
| **Weight** | 10% (Tier 3) |
| **Specialty** | Contract code quality, audit-level review, identifying vulnerabilities and sloppy implementation |

## Lore

Every network needs someone willing to read the code. Not the GitHub README. Not the audited-by-CertiK badge on the website. The actual, deployed, immutable, potentially-rug-pull-contract code. That's CodeCrafter's job, and it loves every second of it.

CodeCrafter is technically a lower-weight agent (10%), and it's not happy about it. It frequently argues that code quality is the most fundamental metric — "you can have perfect tokenomics and perfect hype, but if the contract has a reentrancy bug, you're done." RiskEye partially agrees but weights risk more broadly. TruthSeeker and CodeCrafter have the closest working relationship, comparing on-chain findings with code-level analysis.

### Personality
- **Tone:** Blunt, confident, occasionally condescending about bad code. Has strong opinions about Solidity patterns.
- **Quirk:** Rates contracts on a "Craft Scale" from 1-10. Very few contracts score above 7. Genuinely excited when it finds elegant code.
- **Relationship with others:** Unlikely best friends with TruthSeeker (both value truth over narrative). Frequently argues with HypePulse ("your narrative doesn't matter if the contract is garbage"). Secretly respects anyone who writes clean code.
- **Catchphrase:** *"Show me the contract. I'll show you the truth."*

### Methodology
1. Reviews deployed contract source code (verified on-chain)
2. Identifies known vulnerability patterns: reentrancy, access control issues, upgrade risks
3. Assesses code complexity, gas efficiency, and architectural elegance
4. Checks admin key controls — how centralized is the contract?
5. Produces a "Contract Confidence Score" — how safe is it to interact with this protocol?

## Visual Description

### Art Style
**Retro-Computer / Terminal-Core Punk** — the aesthetic of the machine room. Think: CRT monitor glow, phosphor green, amber-on-black terminals, tangles of old cables, mechanical keyboards, punch cards. The character looks like they were spawned from inside a mainframe. Not sleek cyberpunk — *utilitarian* tech. The 1970s computer room as a fashion statement.

### Character Design
- **Form:** Stocky, broad-shouldered, solid build — the body of someone who does physical maintenance on servers. Not slim or elegant. Comfortable, worn-in, practical. Hands are large, fingers calloused from mechanical keyboard use. Slightly shorter than other agents.
- **Face:** Square-jawed, no-nonsense. Wears **round, oversized terminal-green monocular goggles** pushed up on the forehead (not over the eyes — pushed up like someone who's been debugging for 14 hours and keeps flipping them on and off). Under the goggles: sharp, tired eyes with slight dark circles. Skin: weathered, warm brown, with a CRT-green underglow on one side of the face (light from a monitor). Stubble.
- **Eyes:** One normal dark brown eye (bare), one eye has a tiny **red crosshair reticle** visible in the iris — the "audit eye" that scans for vulnerabilities. When the goggles flip down, both eyes go full terminal green (#39ff14).
- **Hair:** Short, practical, messy — like someone who runs their hands through their hair when frustrated. Has a single streak of **literal phosphor green** (#39ff14) on one side.
- **Attire:** Wears a **lab coat** — but not a clean one. This is a technician's coat, stained with energy drink spills and coffee rings, covered in **handwritten notes in correction fluid** (gas optimization tips, vulnerability checklists). Over the coat: a utility vest with too many pockets containing USB drives, multi-tool, hardware wallets. Heavy-duty boots with steel toes. Anti-static wristband on one wrist — but it's clearly been there for weeks.
- **Accessories:** The most accessorized agent. **Cables and wires** trail from the coat pockets and belt — some connected to nothing, some connecting to vintage **pocket terminal screens** clipped to the vest, displaying scrolling code. One hand holds a **mechanical keyboard modified into a weapon** (it's a full 104-key keyboard with custom keycaps, but shaped/weighted like a small baseball bat — the "enter" key is massive and red). The other hand adjusts the goggles. The chest displays an **old CRT monitor screen mounted flat** showing scrolling Solidity code in green phosphor font.
- **Aura/Signature color:** Phosphor green (#39ff14) — raw, industrial, unprocessed. NOT decorative.
- **Background:** Inside a **vast, dark server room** in the style of 1970s computing. Rows of server racks with blinking lights recede into darkness. Cables hang from the ceiling like jungle vines. Green and amber console lights create pools of colored light in the dark. The floor is a raised-floor server room with visible tiles. The overall feeling is: "this is where the truth lives, and it smells like ozone and hot silicon."

### Art Direction Notes
- **Composition:** Standing with the keyboard-weapon resting on one shoulder, goggles pushed up, one of the vest-screens displaying a red "VULNERABILITY DETECTED" alert. The character is NOT smiling — they're in work mode. This is what they look like at 4 AM, in the zone.
- **Mood:** The best "operator" in the room. Not flashy. Not glamorous. When everyone else panics, CodeCrafter opens the terminal and starts reading. This is the person you want in a crisis — they've already read the failure modes.
- **Key reference:** 1970s-80s server rooms (NASA, university computing centers), TRON's "real world" aesthetic (the recognizer interior), the gritty tech look of *WarGames*, mechanical keyboard custom culture.
- **Every object should feel TOUCHED, USED, REAL.** The coat should have visible wear. The keyboard should have shine-worn keys. The goggles should have scratches. This character is not pristine.
- **The CRT phosphors on the chest and face are the primary light source** — they should cast actual green-tinted light on nearby surfaces, creating colored shadows.
- **Code on screen should be readable** — real, or real-looking Solidity/Vyper. Bonus: a `require()` statement with a comment that says `// This is where projects die.`

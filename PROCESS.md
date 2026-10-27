# Process

## Starting idea

I wanted to make a user-controlled visual interaction that responds to a person's movement without trying to label their emotions. The first version used a webcam and a slow, pale watercolor bloom on a black background. Face position moved the bloom, and the estimated relative distance changed its brightness and size.

## First run and correction

The first install exposed two dependency problems: the pygame package attempted a Windows source build, and the installed OpenCV 5 build did not expose the Haar `CascadeClassifier` API used in the program. With Codex's help, I switched to `pygame-ce` and pinned OpenCV below version 5. I ran the program again and confirmed that it opened normally. The webcam feed is processed locally and is not saved or uploaded.

## User trial and iteration

I asked another person to try the interaction before explaining how the code worked. They tried moving closer, but face detection was difficult. They hesitated because they did not know what the pattern meant and said it was hard to see. This showed me that the response needed a clearer visual identity and a more legible change with distance.

I changed the design from pale watercolor particles to a high-contrast black canvas with neon pink and fluorescent green, sharp fragments, broken horizontal streaks, and faint scanline texture. The artwork is framed as an abstract metaphor for sensory overload, a state some autistic people may experience; it does not claim to depict autistic people or to represent everyone's sensory experience. I also made the on-screen instructions English and more explicit, adjusted the face-area thresholds so the response starts sooner, and shortened the smoothing time. A few faint, fixed glitch lines remain visible when no face is detected, so the idle screen continues the same visual language without flashing. I still need to ask someone to try this revised version and record whether the signal is easier to notice and understand. I will make a further adjustment if that trial reveals a problem.

## AI tools and decisions

I used ChatGPT (Codex) to help edit the Python interaction and draft documentation. I kept the suggestion to use a basic face detector and relative face-box size as a simple input, while avoiding emotion classification because it could make unsupported assumptions about a person's feelings. I changed the initial soft watercolor suggestion after the trial participant could not see or interpret it. The current pattern is designed to remain stable rather than flicker randomly; its brightness and size ease in and out. I will revise this account if I make further changes after the second trial.

## Credits

The face detector is OpenCV's bundled Haar cascade. Pygame drawing utilities are provided by `pygame-ce`. The design direction was informed by a visual reference image supplied during the project discussion; the code uses original procedural shapes and does not copy that image.

## Further trial notes

- Revised version tested by:
- What they tried and what they understood:
- Any discomfort, hesitation, or missed detection:
- Change made after the trial, or why the design was kept:


from pathlib import Path
from PIL import Image

BASE_DIR = Path(__file__).resolve().parent
FACE_DIR = BASE_DIR / "emotion_faces"
OUTPUT_DIR = BASE_DIR / "emotion_gifs"

EMOTIONS = [
    "neutral",
    "joy",
    "sadness",
    "anger",
    "fear",
    "surprise",
    "disgust"
]

OUTPUT_DIR.mkdir(exist_ok=True)


def load_face(emotion):
    path = FACE_DIR / f"{emotion}.png"
    image = Image.open(path).convert("RGBA")

    if image.size != (32, 32):
        raise ValueError(f"{path.name} must be 32x32.")

    # Use black for any transparent background pixels.
    background = Image.new("RGBA", (32, 32), (0, 0, 0, 255))
    return Image.alpha_composite(background, image).convert("RGB")


# Load all faces.
faces = {
    emotion: load_face(emotion)
    for emotion in EMOTIONS
}

# Load blink overlay.
blink = Image.open(
    FACE_DIR / "blink_overlay.png"
).convert("RGBA")

if blink.size != (32, 32):
    raise ValueError("blink_overlay.png must be 32x32.")

neutral = faces["neutral"]

# Create closed-eye Neutral.
closed_eyes = Image.alpha_composite(
    neutral.convert("RGBA"),
    blink
).convert("RGB")


def create_shared_palette(frames):
    """Build one palette using every frame in this animation."""

    atlas = Image.new(
        "RGB",
        (32, 32 * len(frames))
    )

    for index, frame in enumerate(frames):
        atlas.paste(frame, (0, index * 32))

    palette_image = atlas.quantize(
        colors=256,
        method=Image.Quantize.MEDIANCUT,
        dither=Image.Dither.NONE
    )

    return palette_image


def convert_frames_to_shared_palette(frames, palette_image):
    """Convert every frame using exactly the same palette."""

    return [
        frame.quantize(
            palette=palette_image,
            dither=Image.Dither.NONE
        )
        for frame in frames
    ]


for emotion in EMOTIONS:

    target = faces[emotion]
    frames = []

    # 1. Neutral.
    frames.extend([
        neutral.copy(),
        neutral.copy()
    ])

    # 2. Blink.
    frames.extend([
        closed_eyes.copy(),
        closed_eyes.copy()
    ])

    # 3. Smooth crossfade.
    for step in range(1, 11):
        alpha = step / 10
        blended = Image.blend(neutral, target, alpha)
        frames.append(blended)

    # 4. Hold final expression.
    frames.extend([
        target.copy(),
        target.copy(),
        target.copy(),
        target.copy()
    ])

    durations = (
        [160, 160]       # Neutral
        + [100, 100]     # Blink
        + [60] * 10      # Smooth transition (was 80 ms)
        + [250, 250, 250, 1000]  # Hold final expression
    )

    # Build one palette for the entire animation.
    palette_image = create_shared_palette(frames)

    # Convert all frames to that same palette.
    indexed_frames = convert_frames_to_shared_palette(
        frames,
        palette_image
    )

    output_path = OUTPUT_DIR / f"{emotion}_transition.gif"

    indexed_frames[0].save(
        output_path,
        save_all=True,
        append_images=indexed_frames[1:],
        duration=durations,
        palette=bytes(palette_image.getpalette()),
        optimize=False,
        include_color_table=False,
        interlace=False,
        disposal=1
    )

    print(f"Created: {output_path.name}")

print("All seven shared-palette GIFs created!")

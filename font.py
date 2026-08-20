import os

# Font details matching your exact character art specifications
FONT_NAME = "Fluffy Brackets"
CHARACTER_HEIGHT = 4  # Characters are exactly 4 lines high

# FIGlet V2 Header configuration setup for 4-line grids
flf_header = f"flf2a$ {CHARACTER_HEIGHT} 4 20 15 3 0 0 4000\n"
comments = f"{FONT_NAME} custom font package exported for pyfiglet\n"

# 1. Base Numbers 0-9 matching the font's 4-line block layout scale
numbers_data = """
 .---. @
/ .-. \\@
\\ '-' /@
 `---' @@@
 .-.   @
/   |  @

  | |  @
  `-'  @@@
 .---. @
/ .-. \\@
| '-' /@
`---'  @@@
 .---. @
 _..  |@
 ._.-' @
`----' @@@
  .-.  @
 / /|  @
/ /_|  @
`---'  @@@
.----. @
| {_   @
.-._} }@
`----' @@@
 .---. @
/   __}@
\\  {_ }@
 `---\' @@@
.----. @
  / /  @
 / /   @
`--'   @@@
 .---. @
/ .-. \\@
\\ '-' /@
 `---' @@@
 .---. @
/ .-. \\@
`---, /@
   `-' @@@
"""

# 2. Your custom lowercase character blocks from a to z
lowercase_letters = """
  .--.  @
 / {} \\ @
/  /\\  \\@
`-'  `-'@@@
.----. @
| {}  }@
| {}  }@
`----' @@@
 .---. @
/  ___}@
\\     }@
 `---' @@@
.----. @
| {}  \\@
|     /@
`----' @@@
.----.@
| {_  @
| {__ @
`----'@@@
.----.@
| {_  @

| |   @
`-'   @@@
 .---. @
/   __}@
\\  {_ }@
 `---' @@@
.-. .-.\'@

| {_} |@
| { } |@
`-' `-'@@@
.-.@

| |@
| |@
`-'@@@
   .-.@
.-.| |@

| {} |@
`----'@@@
.-. .-.\'@

| |/ / @
| |\\ \\ @
`-' `-'@@@
.-.   @

| |   @
| `--.@
`----'@@@
.-.   .-.@

|  `.'  |@
| |\\ /| |@
`-' ` `-'@@@
.-. .-.\'@

|  `| |@
| |\\  |@
`-' `-'@@@
 .----. @
/  {}  \\@
\\      /@
 `----' @@@
.----. @
| {}  }@
| .--' @
`-'    @@@
 .----. @
/  {}  \\@
\\      /@
 `-----`@@@
.----. @
| {}  }@
| .-. \\@
`-' `-'@@@
 .----.@
{ {__  @
.-._} }@
`----' @@@
 .---. @
{_   _}@

  | |  @
  `-'  @@@
.-. .-.\'@

| { } |@
| {_} |@
`-----\'@@@
.-. .-.\'@

| | | |@
\\ \\_/ /@
 `---' @@@
.-. . .-.@

| |/ \\| |@
|  .'.  |@
`-'   `-'@@@
.-.  .-.@
 \\ \\/ / @
 / /\\ \\ @
`-'  `-'@@@
.-.  .-.@
 \\ \\/ / @
  }  {  @
  `--'  @@@
 .---. @
{_   / @
 /    }@
 `---' @@@
"""

# Assemble structural file content blocks
# FIGlet files require ASCII orders: numbers and special characters come before letters.
full_font_content = flf_header + comments + numbers_data + lowercase_letters

# Duplicate lowercase patterns as uppercase definitions to allow system-wide compatibility
full_font_content += lowercase_letters

# Save layout content variables to disk file
with open(f"{FONT_NAME}.flf", "w", encoding="utf-8") as font_file:
    font_file.write(full_font_content)

print(f"Font compiled successfully: {FONT_NAME}.flf")

# ---------------------------------------------------------------------------
# PyFiglet generator (appended) - preserves above FIGlet content; does not
# delete anything. This builds a mapping `GENERATED_FONT` and helpers for
# importing into `main.py`.
# ---------------------------------------------------------------------------
try:
  import pyfiglet
except Exception:
  pyfiglet = None

# Characters to generate with pyfiglet (uppercase + lowercase + lots of symbols)
PYFIGLET_CHARSET = (
  "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
  "abcdefghijklmnopqrstuvwxyz"
  "0123456789"
  " !@#$%\^&*()~`<>.,?/:;\\|"  # common punctuation
  "_-=+[]{}'\""
  "¿؟¡"
)

PYFIGLET_FONT = "standard"


def build_pyfiglet_font(charset: str = PYFIGLET_CHARSET, figlet_font: str = PYFIGLET_FONT):
  """Render each character in `charset` using pyfiglet and return mapping.

  Returns: dict mapping character -> list of lines (strings).
  """
  if pyfiglet is None:
    raise RuntimeError("pyfiglet is not available. Install it with `pip install pyfiglet`.")

  fig = pyfiglet.Figlet(font=figlet_font)
  rendered = {}
  max_height = 0

  for ch in charset:
    art = fig.renderText(ch)
    lines = art.rstrip("\n").split("\n")
    rendered[ch] = lines
    if len(lines) > max_height:
      max_height = len(lines)

  # Normalize heights and widths
  max_width = 0
  for lines in rendered.values():
    for l in lines:
      if len(l) > max_width:
        max_width = len(l)

  for ch, lines in list(rendered.items()):
    # pad each line to max_width
    padded = [l.ljust(max_width) for l in lines]
    # if shorter than max_height, add empty lines
    for _ in range(max_height - len(padded)):
      padded.append(' ' * max_width)
    rendered[ch] = padded

  return rendered


# Build at import time so `main.py` can `from font import GENERATED_FONT, render_pyfiglet`
GENERATED_FONT = None
if pyfiglet is not None:
  try:
    GENERATED_FONT = build_pyfiglet_font()
  except Exception:
    GENERATED_FONT = None


def render_pyfiglet(text: str, spacer: int = 1) -> str:
  """Render `text` using `GENERATED_FONT`. Falls back to pyfiglet.renderText if needed."""
  if not text:
    return ""

  if GENERATED_FONT is None:
    if pyfiglet is None:
      return text
    # quick fallback
    fig = pyfiglet.Figlet(font=PYFIGLET_FONT)
    return fig.renderText(text)

  # number of lines per char
  height = len(next(iter(GENERATED_FONT.values())))
  out_lines = ['' for _ in range(height)]
  spacer_str = ' ' * spacer
  # Determine width for missing char fallback
  sample_width = len(next(iter(GENERATED_FONT.values()))[0])
  for ch in text:
    art_lines = GENERATED_FONT.get(ch)
    if art_lines is None:
      # if missing, replace with spaces of sample width
      art_lines = [' ' * sample_width for _ in range(height)]
    for i in range(height):
      out_lines[i] += art_lines[i] + spacer_str
  return '\n'.join(out_lines)


if __name__ == '__main__':
  if pyfiglet is None:
    print('pyfiglet is not installed. Install with: pip install pyfiglet')
  else:
    sample = 'Hello, Naze! 123 @#%&()_+-=[]{}'
    print(render_pyfiglet(sample, spacer=1))

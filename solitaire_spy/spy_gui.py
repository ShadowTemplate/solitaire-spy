"""
Auto-generated via ChatGPT

Tkinter Image Grid with 90-degree rotation

Features:
- Displays images in a resizable grid (configurable columns).
- Each image has a label below it.
- Click the image or press the "Rotate" button to rotate that image by 90 degrees clockwise.
- If no images are found in an ./images folder, the script will generate sample images automatically.

Requirements:
- Python 3.8+
- Pillow (install with: pip install pillow)

Run:
python tk_grid_image_rotator.py

"""

import os
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk

from solitaire_spy.constants import CARD_IMAGES_PATH


class PictureTile:
    def __init__(self, parent, pil_image, label_text, card, on_update=None, thumb_size=(200, 600)):
        self.parent = parent
        self.card = card
        self.pil_original = pil_image.convert("RGBA")
        self.angle = 0
        self.on_update = on_update
        self.thumb_size = thumb_size

        # Create UI
        self.frame = ttk.Frame(parent, relief="flat", padding=4)
        self.canvas = tk.Label(self.frame, bd=1, relief="solid")
        self.canvas.pack(expand=False)

        self.text_label = ttk.Label(self.frame, text=label_text)
        self.text_label.pack(fill="x", pady=(6, 0))

        # self.btn_rotate = ttk.Button(self.frame, text="Rotate 90°", command=self.rotate)
        # self.btn_rotate.pack(pady=(6, 0))

        # Bind click on image to rotate
        # self.canvas.bind("<Button-1>", lambda e: self.rotate())

        # Display initial image
        self._update_image()

    def _make_thumbnail(self, pil_img):
        # Create a thumbnail that fits within thumb_size while preserving aspect ratio
        w, h = pil_img.size
        max_w, max_h = self.thumb_size
        ratio = min(max_w / w, max_h / h)
        new_size = (max(1, int(w * ratio)), max(1, int(h * ratio)))
        thumb = pil_img.resize(new_size, Image.LANCZOS)
        return thumb

    def _update_image(self):
        # Rotate from the original to avoid repeated-quality loss
        rotated = self.pil_original.rotate(-self.angle, expand=True)
        thumb = self._make_thumbnail(rotated)

        # Convert to ImageTk
        self.tk_image = ImageTk.PhotoImage(thumb)
        self.canvas.configure(image=self.tk_image)

        if callable(self.on_update):
            self.on_update(self)

    def rotate(self):
        if self.angle == 0:
            self.angle = 90
        else:
            self.angle = 0
        self._update_image()

    def set_label(self, label):
        self.text_label.configure(text=label)
        self.text_label.pack(fill="x", pady=(6, 0))

    def grid(self, row, column):
        self.frame.grid(row=row, column=column, padx=6, pady=6, sticky="n")


class ImageGridApp:
    def __init__(self, root, title, cards, columns=4):
        self.root = root
        self.columns = columns
        self.cards = cards

        self.toolbar = ttk.Frame(root, padding=6)
        self.toolbar.pack(fill="x")

        # self.spin_cols = ttk.Spinbox(self.toolbar, from_=0, to=15, width=3, command=self.redraw)
        # self.spin_cols.set(str(columns))
        ttk.Label(self.toolbar, text=title).pack(side="left", padx=(12, 2))
        # self.spin_cols.pack(side="left")

        self.container = ttk.Frame(root)
        self.container.pack(fill="both", expand=True)

        # Scrollable canvas for the grid
        self.canvas = tk.Canvas(self.container)
        self.scrollbar = ttk.Scrollbar(self.container, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side="right", fill="y")
        # self.canvas.pack(side="left", fill="both", expand=True)

        self.scrollbar = ttk.Scrollbar(self.container, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(xscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side="bottom", fill="x")
        self.canvas.pack(side="left", fill="both", expand=True)
        # self.canvas.pack(side="bottom", fill="both", expand=True)

        self.grid_frame = ttk.Frame(self.canvas)
        self.canvas.create_window((0, 0), window=self.grid_frame, anchor="nw")
        self.grid_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))

        self.tiles = {}
        self.pils = {}
        self.load_images()


    def load_images(self, env=None):
        # Clear existing tiles
        for t in self.tiles.values():
            t.frame.destroy()
        self.tiles = {}

        for card in self.cards:
            if card in self.pils:
                pil = self.pils[card]
            else:
                card_path = f"{CARD_IMAGES_PATH}/{card}.jpg"
                try:
                    pil = Image.open(card_path)
                    self.pils[card] = pil
                except Exception as e:
                    print(f"Failed to open {card_path}: {e}")
                    continue
            label = ""
            tile = PictureTile(self.grid_frame, pil, label, card, thumb_size=(220, 160))
            self.tiles[card] = tile

        self.redraw(env)

    def redraw(self, env=None):
        # Recreate grid layout
        cols = self.columns

        for i, tile_key in enumerate(self.tiles.keys()):
            row = i // cols
            col = i % cols
            tile = self.tiles[tile_key]
            tile.grid(row, col)
            if hasattr(tile_key, "is_tapped"):
                if tile_key.is_tapped:
                    tile.rotate()
            else:
                if env and env.mana_pool:
                    tile.set_label(10 * " " + str(env.mana_pool[tile_key]))

        # update canvas scrollregion
        self.root.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

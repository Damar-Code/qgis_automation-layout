import math
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# Colors — must match the map styling in qgis3.34.10_layout_pid_v02_c1.py
GROWTH_COLOR      = '#33A02C'  # gap_layer 'plant' category (gapsAreaStyle.qml)
GAP_COLOR         = '#F8260B'  # gap_layer 'gaps spot' category (gapsAreaStyle.qml)
NEXT_TARGET_COLOR = '#E2FF9F'  # paddock_cp_layer
SEED_COLOR        = '#FFC986'  # seed_layer
ROAD_COLOR        = '#FF9E17'  # road_layer (RoadGISStyle.qml, 'Main Road' category)
SOIL_REHAB_COLOR  = '#3776B8'  # soil_rehab_layer (soilRehabilitationStyle.qml, single hatch symbol)

# drainage_layer (drainageStyle.qml) is categorized by 'TIPE' into D-1/D-2/D-3
DRAINAGE_CATEGORIES = [
    ('D-1', '#007AFF', 'line'),
    ('D-2', '#00FFC5', 'line'),
    ('D-3', '#C500FF', 'thick_line'),
]


def _render_legend_image(output_path, title, items, dpi=150, fig_w=3.2, title_fontsize=22,
                          label_fontsize=16, max_rows_per_col=None, show_title=True):
    """Shared drawing routine: a bold title followed by one row per item.
    Each item is (label, color, kind), kind one of 'box'/'hatch_box'/'line'/'thick_line'.

    max_rows_per_col : int, optional — once an item list would exceed this
    many rows, it wraps into additional columns (each holding up to this
    many rows) placed side by side, instead of stretching a single column
    ever taller. Swatch/font sizes stay fixed either way — only the number
    of columns changes — so entries always render at a consistent size
    regardless of how many items there are. None (default) keeps the
    original single-column behavior (used by the small base Legend).
    """
    title_h    = 0.7 if show_title else 0.0
    top_margin = 0.15 if show_title else 0.05
    row_h      = 0.6
    swatch_w, swatch_h = 0.9, 0.35
    label_gap  = 0.35
    col_gap    = 0.6

    n_items = len(items)
    if max_rows_per_col and n_items > 0:
        num_cols = math.ceil(n_items / max_rows_per_col)
    else:
        num_cols = 1
    columns = [
        items[c * max_rows_per_col:(c + 1) * max_rows_per_col] if max_rows_per_col else items
        for c in range(num_cols)
    ]
    max_rows = max((len(col) for col in columns), default=0)
    fig_h = title_h + top_margin + (row_h * max_rows) + 0.1

    # ── Measure each column's own longest label, so columns are only as wide
    # as they need to be (uses a scratch figure at the real font size). ─────
    measure_fig = plt.figure()
    measure_ax = measure_fig.add_subplot(111)
    measure_fig.canvas.draw()
    measure_renderer = measure_fig.canvas.get_renderer()

    def text_width_in(text, fs):
        txt = measure_ax.text(0, 0, text, fontsize=fs)
        measure_fig.canvas.draw()
        bbox = txt.get_window_extent(renderer=measure_renderer)
        txt.remove()
        return bbox.width / measure_fig.dpi

    right_padding = 2.0
    col_widths = []
    for col_items in columns:
        max_label_w = max((text_width_in(label, label_fontsize) for label, _, _ in col_items), default=0.0)
        col_widths.append(0.05 + swatch_w + label_gap + max_label_w + right_padding)
    plt.close(measure_fig)

    fig_w = sum(col_widths) + col_gap * max(num_cols - 1, 0)

    fig, ax  = plt.subplots(figsize=(fig_w, fig_h))
    ax.set_xlim(0, fig_w)
    ax.set_ylim(0, fig_h)
    ax.axis('off')

    top_y = fig_h - 0.1
    if show_title:
        ax.text(0.05, top_y - title_h / 2, title,
                ha='left', va='center', fontsize=title_fontsize, fontweight='bold', color='black')

    rows_top = top_y - title_h - top_margin

    col_x = 0.0
    for col_items, col_w in zip(columns, col_widths):
        for i, (label, color, kind) in enumerate(col_items):
            row_y = rows_top - (i * row_h)
            swatch_y = row_y - swatch_h / 2  # vertical center of the swatch area
            x0, x1 = col_x + 0.05, col_x + 0.05 + swatch_w

            if kind == 'none':
                pass  # note row — no swatch, just the label below
            elif kind == 'box':
                swatch = patches.Rectangle(
                    (x0, row_y - swatch_h), swatch_w, swatch_h,
                    linewidth=0, edgecolor='none', facecolor=color
                )
                ax.add_patch(swatch)
            elif kind == 'hatch_box':
                swatch = patches.Rectangle(
                    (x0, row_y - swatch_h), swatch_w, swatch_h,
                    linewidth=0.6, edgecolor=color, facecolor='white',
                    hatch='////',
                )
                ax.add_patch(swatch)
            elif kind == 'thick_line':
                ax.plot([x0, x1], [swatch_y, swatch_y], color=color, linewidth=6, solid_capstyle='butt')
            else:  # 'line'
                ax.plot([x0, x1], [swatch_y, swatch_y], color=color, linewidth=3, solid_capstyle='butt')

            ax.text(
                x1 + label_gap, row_y - swatch_h / 2, label,
                ha='left', va='center', fontsize=label_fontsize, color='black'
            )

        col_x += col_w + col_gap

    plt.savefig(output_path, dpi=dpi, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close()
    print(f"Saved: {output_path}")


def create_legend_image(
    output_path,
    has_seed=True,
    dpi=150,
    include_gap=True,
    include_soil_rehab=False,
):
    """
    Create the standalone base map legend image (title + colored swatches),
    matching the main map's gap/seed/paddock/road/drainage layer colors.

    Parameters
    ----------
    output_path : str  — path to save the legend PNG
    has_seed    : bool — include the 'Seed Production' entry only if True
    dpi         : int  — image resolution
    include_gap : bool — include the 'Growth'/'Gap' entries (gap_layer).
                  Set False for report pages that don't show gap_layer
                  (e.g. the Land Status / Soil Rehabilitation page).
    include_soil_rehab   : bool — add a 'Soil Rehabilitation' entry
                  (hatch-pattern swatch, matching soilRehabilitationStyle.qml).
    """

    items = []
    if include_gap:
        items.append(('Growth', GROWTH_COLOR, 'box'))
        items.append(('Gap', GAP_COLOR, 'box'))
    items.append(('Next Target', NEXT_TARGET_COLOR, 'box'))
    if has_seed:
        items.append(('Seed Production', SEED_COLOR, 'box'))
    if include_soil_rehab:
        items.append(('Soil Rehabilitation', SOIL_REHAB_COLOR, 'hatch_box'))
    items.extend(DRAINAGE_CATEGORIES)

    _render_legend_image(output_path, 'Legend', items, dpi=dpi)


def create_land_status_legend_image(output_path, land_status_items, dpi=150, max_rows_per_col=8):
    """
    Create a dedicated 'Land Application Status' legend image, shown
    separately to the right of the base legend on the Land Application
    Status / Soil Rehabilitation page.

    Parameters
    ----------
    output_path : str — path to save the legend PNG
    land_status_items : list of (label, hex_color) — one entry per Land
                  Status category actually present for this PID, pulled
                  directly from landstatusStyle.qml's categorized renderer
                  (see qgis3.34.10_layout_pid_v03_c2.py). The caller should
                  skip calling this entirely if the list is empty — there is
                  no "no categories" placeholder drawn here. A color of None
                  renders that entry as a plain note row (no swatch) — used
                  for a trailing "+N more categories not shown" line.
    dpi         : int — image resolution
    max_rows_per_col : int — once there are more categories than this, they
                  wrap into additional columns placed side by side (8 per
                  column) instead of shrinking every entry to fit one tall
                  column — keeps swatch/text size standard regardless of PID.
    """
    items = [
        (label, color, 'none' if color is None else 'box')
        for label, color in land_status_items
    ]
    _render_legend_image(output_path, 'Land Application Status', items, dpi=dpi,
                          max_rows_per_col=max_rows_per_col)


# seed_layer's page 2 map color — grey, so it reads as unclassified ground
# rather than competing with the Land Status categories' own colors.
SEED_GREY_COLOR = '#d0d0d0'


def create_seed_legend_image(output_path, dpi=150):
    """
    Create a small, dedicated 'Seed' legend (single grey swatch), shown
    below the Analysis table on page 2 — matches seed_layer's map color.
    """
    items = [('Seed', SEED_GREY_COLOR, 'box')]
    _render_legend_image(output_path, '', items, dpi=dpi,
                          label_fontsize=8, show_title=False)


if __name__ == "__main__":
    create_legend_image(r'D:\legend_test.png', has_seed=True, dpi=150)

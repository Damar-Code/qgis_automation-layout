import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from get_min_max_date import min_max_date_string


def get_classification(growth_pct):
    if growth_pct == '-' or growth_pct is None:
        return ('-', '#FFFFFF', 'black')
    growth_pct = float(growth_pct)
    if growth_pct < 70:
        return ('Replanting',       '#FF0000', 'white')
    elif growth_pct < 80:
        return ('Major Resupply',   '#FF8C00', 'white')
    elif growth_pct < 90:
        return ('Resupply',         '#FFD700', 'black')
    elif growth_pct < 95:
        return ('Acceptable',       '#ADFF2F', 'black')
    else:
        return ('Fully Acceptable', '#228B22', 'white')


def fmt(val):
    if val == '-' or val is None:
        return '-'
    return f"{float(val):.2f}"

def format_planting_periode(oldest_date, newest_date):
    """Return single date if same, range if different."""
    # ── Strip time if exists ──────────────────────────────────────────────────
    oldest_clean = str(oldest_date).split(' ')[0]
    newest_clean = str(newest_date).split(' ')[0]

    if oldest_clean == newest_clean:
        return oldest_date  # single date
    return f'{oldest_date} - {newest_date}'

def _build_rows(pid, gap, planting, commercial_status_value='Commercial Plantation', commercial_date_cutoff=None):
    """Build rows data from gap and planting GeoDataFrames.

    Returns (rows, variety_index_map), where variety_index_map maps each
    variety to the (1)-based index shown in its planting_periode label,
    ordered by that variety's oldest plant_date — the same index used to
    label matching gap_layer features on the map.
    """

    if commercial_date_cutoff is not None:
        # Date-based filter: plant_date on/after the cutoff counts as commercial.
        gap_slct = gap[
            (gap['pid'] == pid)
            & (pd.to_datetime(gap['plant_date']) >= pd.to_datetime(commercial_date_cutoff))
        ]
    else:
        gap_slct = gap[(gap['pid'] == pid) & (gap['Status'] == commercial_status_value)]

    varieties_done = list(set(gap_slct['variety']))

    # ── Order varieties chronologically by their oldest plant_date, so the
    # (1), (2), (3)... index matches planting order ──────────────────────────
    def _oldest_plant_date(var):
        return pd.to_datetime(gap_slct[gap_slct['variety'] == var]['plant_date']).min()

    varieties_done.sort(key=_oldest_plant_date)
    variety_index_map = {var: idx + 1 for idx, var in enumerate(varieties_done)}

    rows = []

    # ── Row per variety with gap result ──────────────────────────────────────
    for var in varieties_done:
        gap_var     = gap_slct[gap_slct['variety'] == var]
        growth_area = sum(gap_var[gap_var['cls'] == 'plant']['cls_area_ha'])
        gap_area    = sum(gap_var[gap_var['cls'] == 'gaps spot']['cls_area_ha'])
        total       = growth_area + gap_area
        growth_pct  = (growth_area / total * 100) if total > 0 else 0
        gap_pct     = (gap_area    / total * 100) if total > 0 else 0

        oldest_date, newest_date = min_max_date_string(
            gdf=gap_var, date_column='plant_date'
        )
        planting_periode = format_planting_periode(oldest_date, newest_date)

        oldest_photo_date, newest_photo_date = min_max_date_string(
            gdf=gap_var, date_column='photo_date'
        )
        photo_periode = format_planting_periode(oldest_photo_date, newest_photo_date)

        rows.append({
            'planting_periode': f"({variety_index_map[var]}) {planting_periode}",
            'photo_periode'   : photo_periode,
            'variety'         : var,
            'growth_area'     : growth_area,
            'growth_pct'      : growth_pct,
            'gap_area'        : gap_area,
            'gap_pct'         : gap_pct
        })

    # ── Row for under_age (not yet monitored) ─────────────────────────────────
    planting_slct = planting[planting['PID'] == pid].copy()
    all_oldest    = pd.to_datetime(gap_slct['plant_date'].max()).tz_localize(None)
    planting_slct['DATE'] = pd.to_datetime(planting_slct['DATE']).dt.tz_localize(None)
    under_age     = planting_slct[planting_slct['DATE'] > all_oldest]

    if not under_age.empty:
        under_age_var = ', '.join(list(set(under_age['VARIETY'])))
        oldest_date_under_age, newest_date_under_age = min_max_date_string(
            gdf=under_age, date_column='DATE'
        )
        rows.append({
            'planting_periode': format_planting_periode(oldest_date_under_age, newest_date_under_age),
            'photo_periode'   : '-',
            'variety'         : under_age_var,
            'growth_area'     : '-',
            'growth_pct'      : '-',
            'gap_area'        : '-',
            'gap_pct'         : '-'
        })

    return rows, variety_index_map


def create_gap_table_image(
    pid                  : str,
    gap                  : object,
    merge_cucp           : object,
    paddok               : object,
    planting             : object,
    output_path          : str,
    dpi                  : int = 150,
    planted_area_override: object = None,
    commercial_status_value: str = 'Commercial Plantation',
    commercial_date_cutoff: object = None,
    include_classification: bool = True,
):
    """
    Create gap detection summary table as image.

    Parameters
    ----------
    pid             : str        — PID value e.g. 'JAGF-2-J-007'
    gap             : GeoDataFrame — gap detection result, with a 'Status' column
                      joined in from the planting database; only rows matching
                      commercial_status_value are included in the summary table
                      (unless commercial_date_cutoff overrides this — see below)
    merge_cucp      : GeoDataFrame — merged CP/CU paddock boundary
    paddok          : GeoDataFrame — paddock landuse layer
    planting        : GeoDataFrame — planting database
    output_path     : str        — path to save image
    dpi             : int        — image resolution
    planted_area_override : float, optional — use this value (hectares) for the
                      Planted Area column instead of computing it from paddok's
                      LANDUSETYP == 'CP' rows. Needed for companies (e.g. MNM)
                      whose paddock layer has no 'CP' landuse type at all.
    commercial_status_value : str — the 'Status' value identifying commercial
                      plantings in this company's planting database. GPA uses
                      'Commercial Plantation'; MNM uses just 'Commercial'.
                      Ignored when commercial_date_cutoff is set.
    commercial_date_cutoff : str/date, optional — if set, rows are selected by
                      plant_date >= this cutoff instead of by Status. Kept as an
                      alternative to commercial_status_value, not a replacement —
                      pass whichever one matches how the caller is filtering
                      gap_layer/seed_layer on the map.
    include_classification : bool — when False, omits the classification
                      legend table drawn to the right of the value table
                      (the per-row "Classification" column in the value
                      table itself is unaffected). Used for report pages
                      that show their own legend in that space instead.

    Returns
    -------
    variety_index_map : dict — variety -> (1)-based index shown in the
                         planting_periode label, for labeling matching
                         gap_layer features on the map with the same number.
    """

    # ── Compute area values ───────────────────────────────────────────────────
    total_area = round(merge_cucp[merge_cucp['PID'] == pid].area.sum() / 10000, 2)
    if planted_area_override is not None:
        planted_area = round(planted_area_override, 2)
    else:
        planted_area = round(
            sum(paddok[(paddok['PID'] == pid) & (paddok['LANDUSETYP'] == 'CP')].area / 10000), 2
        )

    # ── Build rows ────────────────────────────────────────────────────────────
    rows, variety_index_map = _build_rows(
        pid, gap, planting,
        commercial_status_value=commercial_status_value,
        commercial_date_cutoff=commercial_date_cutoff
    )
    n_rows = len(rows)

    # ── Classification legend table (drawn to the right of the value table) ──
    classification_rows = [
        ('< 70 %',       'Replanting'),
        ('70 % - 80 %',  'Major Resupply'),
        ('80 % - 90 %',  'Resupply'),
        ('90 % - 95 %',  'Acceptable'),
        ('95 % - 100 %', 'Fully Acceptable'),
    ]
    cls_col1_w    = 1.3
    cls_col2_w    = 2.3
    cls_table_w   = (cls_col1_w + cls_col2_w) if include_classification else 0.0
    cls_header_h  = 0.35
    cls_row_h     = 0.3
    cls_note_h    = 0.35
    cls_table_h   = cls_header_h + (cls_row_h * len(classification_rows)) + cls_note_h

    # ── Figure setup ──────────────────────────────────────────────────────────
    table_w      = 13.7
    gap_w        = 0.15 if include_classification else 0.0
    right_margin = 0.15  # keeps the classification table's right border off the clip edge
    fig_w    = table_w + gap_w + cls_table_w + right_margin
    header_h = 0.4
    row_h    = 0.3
    fig_h    = max(header_h + (row_h * n_rows) + 0.4, (cls_table_h + 0.4) if include_classification else 0.0)

    fig, ax  = plt.subplots(figsize=(fig_w, fig_h))
    ax.set_xlim(0, fig_w)
    ax.set_ylim(0, fig_h)
    ax.axis('off')

    # ── Colors ────────────────────────────────────────────────────────────────
    header_color = '#DCE6F1'
    cell_color   = '#FFFFFF'
    alt_color    = '#FFFFFF'

    # ── Columns ───────────────────────────────────────────────────────────────
    cols = [
        (0.00,  1.20, 'PID'),
        (1.20,  0.90, 'Total\nArea (Ha)'),
        (2.10,  0.90, 'Planted\nArea (Ha)'),
        (3.00,  2.20, 'Planting\nPeriode'),
        (5.20,  2.60, 'Photo\nPeriode'),
        (7.80,  0.80, 'Variety'),
        (8.60,  0.90, 'Growth\nArea (Ha)'),
        (9.50,  0.90, 'Gap\nArea (Ha)'),
        (10.40, 0.75, 'Growth\n%'),
        (11.15, 0.75, 'Gap\n%'),
        (11.90, 1.50, 'Classification'),
    ]

    top_y = fig_h - 0.2

    def draw_cell(x, y, w, h, text, bg, fc='black', bold=False, fontsize=8):
        rect = patches.Rectangle(
            (x, y - h), w, h,
            linewidth=0.5, edgecolor='black', facecolor=bg
        )
        ax.add_patch(rect)
        ax.text(
            x + w / 2, y - h / 2, text,
            ha='center', va='center', fontsize=fontsize,
            color=fc, fontweight='bold' if bold else 'normal'
        )

    # ── Header ────────────────────────────────────────────────────────────────
    for x, w, label in cols:
        draw_cell(x, top_y, w, header_h, label,
                  bg=header_color, fc='black', bold=True, fontsize=8)

    # ── Merged cells: PID, Total Area, Planted Area ───────────────────────────
    merged_h   = row_h * n_rows
    merged_top = top_y - header_h

    for x, w, _ in cols[:3]:
        val = (
            pid                   if x == 0.00 else
            f"{total_area:.2f}"   if x == 1.20 else
            f"{planted_area:.2f}"
        )
        draw_cell(x, merged_top, w, merged_h,
                  val, bg=cell_color, fc='black', fontsize=8)

    # ── Data rows ─────────────────────────────────────────────────────────────
    for i, row in enumerate(rows):
        row_y      = merged_top - (i * row_h)
        bg         = alt_color if i % 2 != 0 else cell_color
        growth_pct = row.get('growth_pct', 0)

        cls_label, _cls_color, _cls_fc = get_classification(growth_pct)

        values = [
            row.get('planting_periode', ''),
            row.get('photo_periode', ''),
            row.get('variety', ''),
            fmt(row.get('growth_area')),
            fmt(row.get('gap_area')),
            fmt(row.get('growth_pct')),
            fmt(row.get('gap_pct')),
        ]

        for j, (x, w, _) in enumerate(cols[3:-1]):
            draw_cell(x, row_y, w, row_h, values[j],
                      bg=bg, fc='black', fontsize=8)

        # Classification: no colored background — just bold black text.
        cls_x_col, cls_w_col, _ = cols[-1]
        draw_cell(cls_x_col, row_y, cls_w_col, row_h, cls_label,
                  bg=bg, fc='black', bold=True, fontsize=8)

    # ── Classification legend table ────────────────────────────────────────
    if include_classification:
        cls_table_x = table_w + gap_w
        cls_top_y   = top_y

        draw_cell(cls_table_x, cls_top_y, cls_table_w, cls_header_h, 'Classification',
                  bg='#FFFFFF', fc='black', bold=True, fontsize=10)

        cls_rows_top = cls_top_y - cls_header_h
        for i, (pct_range, label) in enumerate(classification_rows):
            row_y = cls_rows_top - (i * cls_row_h)
            draw_cell(cls_table_x, row_y, cls_col1_w, cls_row_h, pct_range,
                      bg='#FFFFFF', fc='black', fontsize=9)
            draw_cell(cls_table_x + cls_col1_w, row_y, cls_col2_w, cls_row_h, label,
                      bg='#FFFFFF', fc='black', bold=True, fontsize=9)

        note_y = cls_rows_top - (len(classification_rows) * cls_row_h)
        draw_cell(cls_table_x, note_y, cls_table_w, cls_note_h,
                  'Note : Classification By Growth Percentage',
                  bg='#FFFFFF', fc='black', fontsize=7)

    plt.tight_layout(pad=0.1)
    plt.savefig(output_path, dpi=dpi, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close()
    print(f"✅ Saved: {output_path}")

    return variety_index_map


def _render_simple_table_image(headers, rows, output_path, dpi=150, fontsize=11,
                                header_h=0.55, row_h=0.5, cell_padding=1.0,
                                col_width_scale=1.0):
    """
    Shared drawing routine for a small summary table: a bold shaded header
    row above one or more value rows, each column sized to its own content
    (header lines + the widest value in that column) instead of a fixed
    shared width.

    Parameters
    ----------
    headers : list of str — column headers (may contain '\\n' for 2 lines)
    rows    : list of list of str — one inner list per data row, same
              length/order as headers
    header_h, row_h : float — header/row heights in inches. Smaller values
              keep tables with many rows (e.g. the Operation summary) from
              growing tall enough to overflow the page.
    """
    header_color = '#DCE6F1'
    cell_color   = '#FFFFFF'

    measure_fig = plt.figure()
    measure_ax = measure_fig.add_subplot(111)
    measure_fig.canvas.draw()
    renderer = measure_fig.canvas.get_renderer()

    def text_width_in(text, fs, bold=False):
        txt = measure_ax.text(0, 0, text, fontsize=fs, fontweight='bold' if bold else 'normal')
        measure_fig.canvas.draw()
        bbox = txt.get_window_extent(renderer=renderer)
        txt.remove()
        return bbox.width / measure_fig.dpi

    col_widths = []
    for col_idx, header in enumerate(headers):
        header_w = max(text_width_in(line, fontsize, bold=True) for line in header.split('\n'))
        value_w  = max((text_width_in(row[col_idx], fontsize) for row in rows), default=0.0)
        col_widths.append((max(header_w, value_w) + cell_padding) * col_width_scale)
    plt.close(measure_fig)

    cols = []
    x = 0.0
    for header, w in zip(headers, col_widths):
        cols.append((x, w, header))
        x += w
    table_w = x
    # A little extra canvas past the last column's right edge — otherwise its
    # border sits exactly on the axes' clip boundary and gets clipped away by
    # bbox_inches='tight' (same fix as the classification table's right_margin
    # in create_gap_table_image).
    right_margin = 0.15
    fig_w = table_w + right_margin

    fig_h    = header_h + (row_h * len(rows)) + 0.2

    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.set_xlim(0, fig_w)
    ax.set_ylim(0, fig_h)
    ax.axis('off')

    top_y = fig_h - 0.1

    def draw_cell(x, y, w, h, text, bg, fc='black', bold=False, fontsize=11):
        rect = patches.Rectangle(
            (x, y - h), w, h,
            linewidth=0.5, edgecolor='black', facecolor=bg
        )
        ax.add_patch(rect)
        ax.text(
            x + w / 2, y - h / 2, text,
            ha='center', va='center', fontsize=fontsize,
            color=fc, fontweight='bold' if bold else 'normal'
        )

    for x, w, label in cols:
        draw_cell(x, top_y, w, header_h, label,
                  bg=header_color, fc='black', bold=True, fontsize=fontsize)

    for i, row in enumerate(rows):
        row_y = top_y - header_h - (i * row_h)
        for (x, w, _), value in zip(cols, row):
            draw_cell(x, row_y, w, row_h, value, bg=cell_color, fc='black', fontsize=fontsize)

    plt.savefig(output_path, dpi=dpi, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close()
    print(f"✅ Saved: {output_path}")


def create_land_application_table_image(
    planted_area_ha,
    soil_rehab_area_ha,
    land_status_area_ha,
    output_path,
    dpi=150,
):
    """
    Create the page 2 (Land Application Status) summary table image: Planted
    area alongside Soil Rehabilitation and Land Application Status areas
    (Ha). Same visual styling (header shading, borders, fonts) as the main
    germination summary table.

    Parameters
    ----------
    planted_area_ha      : float — total planting_gdf area for this PID (Ha)
    soil_rehab_area_ha   : float — soil_rehab_gdf area clipped to this PID (Ha)
    land_status_area_ha  : float — land_status_gdf area for this PID (Ha)
    output_path          : str   — path to save the image
    dpi                  : int   — image resolution
    """
    headers = ['Planted\n(Ha)', 'Soil Rehabilitation\n(Ha)', 'Land Application Status\n(Ha)']
    rows = [[
        f"{planted_area_ha:.2f}",
        f"{soil_rehab_area_ha:.2f}",
        f"{land_status_area_ha:.2f}",
    ]]
    _render_simple_table_image(headers, rows, output_path, dpi=dpi)


def create_operation_summary_table_image(
    operation_areas_ha,
    output_path,
    dpi=150,
):
    """
    Create an Operation/Ha summary table — one row per operation, e.g.
    ('LD-Ripper', 19.20) — total area (Ha) that operation covers for this
    PID. Same visual styling as create_land_application_table_image.

    Parameters
    ----------
    operation_areas_ha : list of (str, float) — operation name -> area (Ha),
                          in the order they should appear as rows
    output_path         : str — path to save the image
    dpi                  : int — image resolution
    """
    headers = ['Operation', 'Ha']
    rows = [[name, f"{area_ha:.2f}"] for name, area_ha in operation_areas_ha]
    _render_simple_table_image(headers, rows, output_path, dpi=dpi,
                                fontsize=13, header_h=0.6, row_h=0.5)


def create_analysis_summary_table_image(
    analysed_area_ha,
    growth_area_ha,
    gap_area_ha,
    growth_pct,
    output_path,
    dpi=150,
):
    """
    Create an Analysis summary table — Analysed/Growth/Gap area (Ha) and
    Growth % for this PID's commercial plantings. Same visual styling and
    sizing (fontsize/row height) as the Operation summary table, since both
    sit side by side on page 2.

    Parameters
    ----------
    analysed_area_ha : float — total analysed area (growth + gap), Ha
    growth_area_ha    : float — growth area, Ha
    gap_area_ha       : float — gap area, Ha
    growth_pct        : float — growth area as a percentage of analysed area
    output_path       : str — path to save the image
    dpi               : int — image resolution
    """
    headers = ['Analysed Ha', 'Growth Ha', 'Gap Ha', 'Growth %']
    rows = [[
        f"{analysed_area_ha:.2f}",
        f"{growth_area_ha:.2f}",
        f"{gap_area_ha:.2f}",
        f"{growth_pct:.2f}",
    ]]
    _render_simple_table_image(headers, rows, output_path, dpi=dpi,
                                fontsize=13, header_h=0.6, row_h=0.5, cell_padding=0.5,
                                col_width_scale=1.2)


if __name__ == "__main__":
    # ── Usage ─────────────────────────────────────────────────────────────────
    import geopandas as gpd
    from planting_handler import planting_handler

    planting_gdb_path       = r"D:\automation of gap and weed detection\database\GPA\20_planting.gdb"
    landuse_gdb_path        = r"D:\automation of gap and weed detection\database\GPA\60_landuse.gdb"
    gpkg_gaps_planting_path = r"D:\automation of gap and weed detection\database\GPA\Gaps-Detection_GPA_Planting_AR.gpkg"
    merge_cucp_path         = r'D:\automation of gap and weed detection\database\GPA\paddock_cucp.gpkg'

    merge_cucp = gpd.read_file(merge_cucp_path)
    paddok     = gpd.read_file(landuse_gdb_path, layer='paddock')
    gap        = gpd.read_file(gpkg_gaps_planting_path, layer='Gaps-Detection_GPA_20260915_Planting_AR')
    planting   = planting_handler(planting_gdb_path)

    create_gap_table_image(
        pid         = 'JAGF-2-G-009',
        gap         = gap,
        merge_cucp  = merge_cucp,
        paddok      = paddok,
        planting    = planting,
        output_path = r'D:\gap_table_JAGF-2-G-009.png',
        dpi         = 150
    )



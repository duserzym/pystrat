DEFAULT_PYCAIRO_STYLE = {
    'font_family': 'DejaVu Sans',
    'font_weight': 'normal',
    'font_style': 'normal',
    'text_color': (0.15, 0.15, 0.15),
    'tick_text_size': 8.5,
    'unit_text_size': 8.5,
    'annotation_text_size': 8.5,
    'axis_label_size': 9.0,
    'tick_label_x_pad': 26.0,
    'tick_label_baseline_shift': 3.0,
    'axis_line_width': 0.9,
    'tick_line_width': 0.9,
    'bed_border_width': 0.7,
    'frame_line_width': 0.7,
    'data_line_width': 1.1,
    'data_point_radius': 1.9,
    'tick_len': 4.5,
}

def _as_rgb(color, fallback=(0.15, 0.15, 0.15)):
    if color is None:
        return fallback
    if isinstance(color, str):
        c = color.strip()
        if c.startswith('#') and len(c) in (7, 9):
            return (int(c[1:3], 16) / 255.0, int(c[3:5], 16) / 255.0, int(c[5:7], 16) / 255.0)
        return fallback
    if isinstance(color, (tuple, list)) and len(color) >= 3:
        return (float(color[0]), float(color[1]), float(color[2]))
    return fallback


def _to_cairo_weight(weight):
    if weight is None:
        return cairo.FONT_WEIGHT_NORMAL
    w = str(weight).strip().lower()
    if w in {'bold', 'semibold', 'demibold', 'heavy', 'black', '700', '800', '900'}:
        return cairo.FONT_WEIGHT_BOLD
    return cairo.FONT_WEIGHT_NORMAL


def _to_cairo_slant(style):
    if style is None:
        return cairo.FONT_SLANT_NORMAL
    s = str(style).strip().lower()
    if s == 'italic':
        return cairo.FONT_SLANT_ITALIC
    if s == 'oblique':
        return cairo.FONT_SLANT_OBLIQUE
    return cairo.FONT_SLANT_NORMAL


def _normalize_text_kwargs(text_kwargs):
    cfg = {}
    if not text_kwargs:
        return cfg
    family = text_kwargs.get('fontfamily', text_kwargs.get('family'))
    if isinstance(family, (list, tuple)) and len(family) > 0:
        family = family[0]
    if family is not None:
        cfg['font_family'] = str(family)
    fontsize = text_kwargs.get('fontsize', text_kwargs.get('size'))
    if fontsize is not None:
        cfg['base_font_size'] = float(fontsize)
    weight = text_kwargs.get('fontweight', text_kwargs.get('weight'))
    if weight is not None:
        cfg['font_weight'] = str(weight)
    style = text_kwargs.get('fontstyle', text_kwargs.get('style'))
    if style is not None:
        cfg['font_style'] = str(style)
    if 'color' in text_kwargs:
        cfg['text_color'] = _as_rgb(text_kwargs['color'], fallback=(0.15, 0.15, 0.15))
    return cfg


def _render_svg_tiled(ctx, svg_path, x, y, width, height, tile_width, tile_offset=(0.0, 0.0)):
    if not svg_path.exists() or tile_width <= 0:
        return

    handle = Rsvg.Handle.new_from_file(str(svg_path))
    dims = handle.get_dimensions()
    if dims.width == 0 or dims.height == 0:
        return

    scale = tile_width / dims.width
    tile_height = dims.height * scale
    if tile_height <= 0:
        return

    offset_x, offset_y = tile_offset
    offset_x = offset_x % tile_width if tile_width else 0.0
    offset_y = offset_y % tile_height if tile_height else 0.0

    x_start = x - offset_x - tile_width
    y_start = y - offset_y - tile_height

    ctx.save()
    ctx.rectangle(x, y, width, height)
    ctx.clip()

    y0 = y_start
    while y0 < y + height + tile_height:
        x0 = x_start
        while x0 < x + width + tile_width:
            ctx.save()
            ctx.translate(x0, y0)
            ctx.scale(scale, scale)
            handle.render_cairo(ctx)
            ctx.restore()
            x0 += tile_width
        y0 += tile_height
    ctx.restore()


def _unit_intervals(values, cum_heights):
    intervals = []
    start_idx = 0
    for i in range(1, len(values) + 1):
        if i == len(values) or values[i] != values[start_idx]:
            intervals.append((values[start_idx], cum_heights[start_idx], cum_heights[i]))
            start_idx = i
    return intervals


def _resolve_style(figsize, font_scale='auto', style_overrides=None, text_kwargs=None, text_size_overrides=None):
    cfg = dict(DEFAULT_PYCAIRO_STYLE)
    if style_overrides is not None:
        cfg.update(style_overrides)
    if text_kwargs:
        for k, v in _normalize_text_kwargs(text_kwargs).items():
            cfg[k] = v

    fig_w_in, fig_h_in = figsize
    size_factor = max(0.8, np.sqrt((fig_w_in * fig_h_in) / (2.0 * 7.0)))
    scale = 1.2 * size_factor if font_scale == 'auto' else float(font_scale)
    if scale <= 0:
        raise ValueError("font_scale must be > 0, or use font_scale='auto'")

    cfg['font_scale'] = scale
    base_font_size = float(cfg.get('base_font_size', cfg['tick_text_size']))
    cfg['tick_text_size'] = base_font_size
    cfg['unit_text_size'] = base_font_size
    cfg['annotation_text_size'] = base_font_size
    cfg['axis_label_size'] = base_font_size + 0.5
    cfg['data_title_text_size'] = base_font_size
    cfg['data_xlabel_text_size'] = max(6.0, base_font_size - 0.5)

    if text_size_overrides:
        cfg.update(text_size_overrides)

    for key in ['tick_text_size', 'unit_text_size', 'annotation_text_size', 'axis_label_size',
                'data_title_text_size', 'data_xlabel_text_size',
                'tick_label_x_pad', 'tick_label_baseline_shift', 'tick_len']:
        cfg[key] *= scale
    for key in ['axis_line_width', 'tick_line_width', 'bed_border_width', 'frame_line_width', 'data_line_width', 'data_point_radius']:
        cfg[key] *= max(0.85, np.sqrt(scale))

    return cfg


def _draw_text(ctx, x, y, text, size, style_cfg, weight=None, slant=None, color=None):
    w = _to_cairo_weight(style_cfg.get('font_weight') if weight is None else weight)
    s = _to_cairo_slant(style_cfg.get('font_style') if slant is None else slant)
    c = _as_rgb(color, fallback=style_cfg.get('text_color', (0.15, 0.15, 0.15)))
    ctx.select_font_face(style_cfg['font_family'], s, w)
    ctx.set_font_size(size)
    ctx.set_source_rgb(*c)
    ctx.move_to(x, y)
    ctx.show_text(str(text))


def _draw_data_track(ctx, x_left, y_top, width, height, y_min, y_max, values, heights, title, xlabel, style_cfg):
    vals = np.asarray(values, dtype=float)
    zs = np.asarray(heights, dtype=float)
    mask = np.isfinite(vals) & np.isfinite(zs) & (zs >= y_min) & (zs <= y_max)
    vals, zs = vals[mask], zs[mask]
    if len(vals) == 0:
        return

    pad_x = 10 * style_cfg['font_scale']
    pad_top = 10 * style_cfg['font_scale']
    pad_bottom = 18 * style_cfg['font_scale']
    left, right = x_left + pad_x, x_left + width - pad_x
    top, bottom = y_top + pad_top, y_top + height - pad_bottom

    v_min, v_max = np.nanmin(vals), np.nanmax(vals)
    if np.isclose(v_min, v_max):
        v_min -= 1.0
        v_max += 1.0
    v_pad = 0.05 * (v_max - v_min)
    v_min -= v_pad
    v_max += v_pad

    def xmap(v):
        return left + (v - v_min) * (right - left) / (v_max - v_min)

    def ymap(z):
        return bottom - (z - y_min) * (bottom - top) / (y_max - y_min)

    ctx.rectangle(left, top, right - left, bottom - top)
    ctx.set_source_rgb(0.2, 0.2, 0.2)
    ctx.set_line_width(style_cfg['frame_line_width'])
    ctx.stroke()

    order = np.argsort(zs)
    vals, zs = vals[order], zs[order]
    ctx.set_source_rgb(0.15, 0.3, 0.65)
    ctx.set_line_width(style_cfg['data_line_width'])
    for i, (v, z) in enumerate(zip(vals, zs)):
        x, y = xmap(v), ymap(z)
        if i == 0:
            ctx.move_to(x, y)
        else:
            ctx.line_to(x, y)
    ctx.stroke()

    ctx.set_source_rgb(0.1, 0.1, 0.1)
    for v, z in zip(vals, zs):
        ctx.arc(xmap(v), ymap(z), style_cfg['data_point_radius'], 0, 2 * np.pi)
        ctx.fill()

    _draw_text(ctx, left, top - 2 * style_cfg['font_scale'], title, style_cfg.get('data_title_text_size', 8.5 * style_cfg['font_scale']), style_cfg, weight='bold')
    _draw_text(ctx, left, bottom + 12 * style_cfg['font_scale'], xlabel, style_cfg.get('data_xlabel_text_size', 8.0 * style_cfg['font_scale']), style_cfg)


def draw_vector_panel_examples(
    output_path,
    mode='group_labels',
    surface='svg',
    swatch_density_scale=1.0,
    swatch_tile_factor=0.30,
    swatch_min_tile_width=12.0,
    swatch_offset=(0.0, 0.0),
    y_limits=(0, 120),
    figsize=None,
    font_scale='auto',
    text_kwargs=None,
    text_size_overrides=None,
    tick_interval=20.0,
    style_overrides=None,
    annotation_size_override=None,
    y_title='stratigraphic height',
    y_unit='m',
    show=True,
):
    if mode in ('group_labels', 'annotations', 'annotation_size') and figsize is None:
        figsize = (2.5, 7.0)
    elif mode == 'strat_data' and figsize is None:
        figsize = (5.0, 9.0)

    if mode not in ('group_labels', 'annotations', 'annotation_size', 'strat_data'):
        raise ValueError("mode must be one of: 'group_labels', 'annotations', 'annotation_size', 'strat_data'")

    y_min, y_max = y_limits
    fig_w_in, fig_h_in = figsize
    width_pt, height_pt = fig_w_in * 72.0, fig_h_in * 72.0
    style_cfg = _resolve_style(
        figsize,
        font_scale=font_scale,
        style_overrides=style_overrides,
        text_kwargs=text_kwargs,
        text_size_overrides=text_size_overrides,
    )

    if surface == 'pdf':
        surf = cairo.PDFSurface(str(output_path), width_pt, height_pt)
    elif surface == 'svg':
        surf = cairo.SVGSurface(str(output_path), width_pt, height_pt)
    else:
        raise ValueError("surface must be 'pdf' or 'svg'")

    ctx = cairo.Context(surf)
    ctx.set_source_rgb(1, 1, 1)
    ctx.paint()

    style_lookup = style_df.set_index('facies')
    svg_dir = Path('../swatches/SVG')
    ann_df = pd.read_csv('example-data/annotations.csv')
    chemo_df = pd.read_csv('example-data/chemostratigraphy.csv')

    scale = style_cfg['font_scale']
    # Horizontal space reserved left of strat beds for axis labels and y_title
    _title_band = (style_cfg['axis_label_size'] + 6 * scale) if y_title else 0
    _axis_col_offset = _title_band + style_cfg['tick_label_x_pad'] + 8  # 8 = axis-to-col gap

    if mode == 'strat_data':
        panel_margin = 12 * scale
        section_left = panel_margin
        total_w = width_pt - 2 * panel_margin
        gap = 10 * scale
        section_w = 0.50 * total_w
        data_w = (total_w - section_w - 2 * gap) / 2.0
        y_top = panel_margin
        y_span = height_pt - 2 * panel_margin
    else:
        panel_margin = 10 * scale
        section_left = panel_margin
        # Extra top space so group/formation column headers render inside the figure
        _header_band = (style_cfg['unit_text_size'] + 6 * scale) if mode == 'group_labels' else 0
        y_top = panel_margin + _header_band
        y_span = height_pt - y_top - panel_margin
        section_w = width_pt - 2 * panel_margin

    # Column beds start after the axis area
    col_left = section_left + _axis_col_offset
    col_right_max = col_left
    # Available content width after reserving axis area
    _content_w = section_w - _axis_col_offset

    thickness = litho_df['THICKNESS'].to_numpy()
    facies = litho_df['FACIES'].to_numpy()
    cum_heights = np.r_[0.0, np.cumsum(thickness)]
    y_scale = y_span / (y_max - y_min)

    max_col_w = _content_w * (0.52 if mode == 'group_labels' else 0.65)
    width_scale = max_col_w / style_lookup['width'].max()

    for i, fac in enumerate(facies):
        z0, z1 = cum_heights[i], cum_heights[i + 1]
        if z1 <= y_min or z0 >= y_max:
            continue

        draw_top, draw_bot = max(z0, y_min), min(z1, y_max)
        bed_h = (draw_bot - draw_top) * y_scale
        if bed_h <= 0:
            continue

        y0 = y_top + y_span - (draw_bot - y_min) * y_scale
        bed_w = style_lookup.loc[fac, 'width'] * width_scale
        col_right_max = max(col_right_max, col_left + bed_w)

        r, g, b = style_lookup.loc[fac, ['R', 'G', 'B']].to_numpy() / 255.0
        ctx.rectangle(col_left, y0, bed_w, bed_h)
        ctx.set_source_rgb(r, g, b)
        ctx.fill_preserve()
        ctx.set_source_rgb(0.2, 0.2, 0.2)
        ctx.set_line_width(style_cfg['bed_border_width'])
        ctx.stroke()

        swatch_id = int(style_lookup.loc[fac, 'swatch'])
        if swatch_id != 0:
            svg_path = svg_dir / f'{swatch_id}.svg'
            base_tile_width = max(swatch_min_tile_width, bed_w * swatch_tile_factor)
            tile_w = base_tile_width / max(swatch_density_scale, 1e-6)
            _render_svg_tiled(ctx, svg_path, col_left, y0, bed_w, bed_h, tile_w, tile_offset=swatch_offset)

        ctx.rectangle(col_left, y0, bed_w, bed_h)
        ctx.set_source_rgb(0.15, 0.15, 0.15)
        ctx.set_line_width(style_cfg['bed_border_width'])
        ctx.stroke()

    axis_x = col_left - 8  # vertical axis line, just left of bed column
    ctx.set_source_rgb(0.1, 0.1, 0.1)
    ctx.set_line_width(style_cfg['axis_line_width'])
    ctx.move_to(axis_x, y_top)
    ctx.line_to(axis_x, y_top + y_span)
    ctx.stroke()

    # Ticks + right-aligned tick labels (end 4pt from axis)
    tick_start = np.ceil(y_min / tick_interval) * tick_interval
    ticks = np.arange(tick_start, y_max + 0.5 * tick_interval, tick_interval)
    for t in ticks:
        y_t = y_top + y_span - (t - y_min) * y_scale
        if y_t < y_top + 0.5 or y_t > y_top + y_span - 0.5:
            continue
        ctx.set_line_width(style_cfg['tick_line_width'])
        ctx.move_to(axis_x - style_cfg['tick_len'], y_t)
        ctx.line_to(axis_x, y_t)
        ctx.stroke()
        tick_label = f'{int(t)}'
        ctx.save()
        ctx.select_font_face(style_cfg['font_family'],
                             _to_cairo_slant(style_cfg.get('font_style')),
                             _to_cairo_weight(style_cfg.get('font_weight')))
        ctx.set_font_size(style_cfg['tick_text_size'])
        tte = ctx.text_extents(tick_label)
        ctx.restore()
        _draw_text(ctx, axis_x - 4 * scale - tte[2],
                   y_t + style_cfg['tick_label_baseline_shift'],
                   tick_label, style_cfg['tick_text_size'], style_cfg)

    # Unit label: right-aligned, above the topmost tick line
    if y_unit:
        unit_text = f'({y_unit})'
        ctx.save()
        ctx.select_font_face(style_cfg['font_family'],
                             _to_cairo_slant(style_cfg.get('font_style')),
                             _to_cairo_weight(style_cfg.get('font_weight')))
        ctx.set_font_size(style_cfg['axis_label_size'])
        ute = ctx.text_extents(unit_text)
        ctx.restore()
        _draw_text(ctx, axis_x - 4 * scale - ute[2],
                   y_top + style_cfg['axis_label_size'],
                   unit_text, style_cfg['axis_label_size'], style_cfg)

    # Y-axis title: rotated 90° (reads upward), centered in the title band and along y_span
    if y_title:
        ctx.save()
        ctx.select_font_face(style_cfg['font_family'],
                             _to_cairo_slant(style_cfg.get('font_style')),
                             _to_cairo_weight(style_cfg.get('font_weight')))
        ctx.set_font_size(style_cfg['axis_label_size'])
        te = ctx.text_extents(y_title)
        title_cx = section_left + _title_band / 2
        ctx.translate(title_cx, y_top + y_span / 2)
        ctx.rotate(-np.pi / 2)
        ctx.set_source_rgb(*style_cfg.get('text_color', (0.15, 0.15, 0.15)))
        ctx.move_to(-te[2] / 2, te[3] / 2)
        ctx.show_text(y_title)
        ctx.restore()

    if mode == 'group_labels':
        unit_cols = ('GROUP', 'FORMATION')
        track_gap = 6 * style_cfg['font_scale']
        unit_track_left = col_right_max + 8
        unit_track_w = max(14 * style_cfg['font_scale'], (section_left + section_w - unit_track_left - (len(unit_cols) - 1) * track_gap) / len(unit_cols))

        for j, col_name in enumerate(unit_cols):
            if col_name not in litho_df.columns:
                continue
            x0 = unit_track_left + j * (unit_track_w + track_gap)
            intervals = _unit_intervals(litho_df[col_name].astype(str).to_numpy(), cum_heights)
            for label, z_top, z_bot in intervals:
                if z_bot <= y_min or z_top >= y_max:
                    continue
                draw_top, draw_bot = max(z_top, y_min), min(z_bot, y_max)
                y1 = y_top + y_span - (draw_bot - y_min) * y_scale
                hh = (draw_bot - draw_top) * y_scale
                ctx.rectangle(x0, y1, unit_track_w, hh)
                ctx.set_source_rgba(0.97, 0.97, 0.97, 1.0)
                ctx.fill_preserve()
                ctx.set_source_rgb(0.2, 0.2, 0.2)
                ctx.set_line_width(style_cfg['frame_line_width'])
                ctx.stroke()
                # Draw interval label: rotate 90° when text is too wide for the box
                if hh > 5 * scale:
                    ctx.save()
                    ctx.select_font_face(style_cfg['font_family'],
                                         _to_cairo_slant(style_cfg.get('font_style')),
                                         _to_cairo_weight(style_cfg.get('font_weight')))
                    ctx.set_font_size(style_cfg['unit_text_size'])
                    lte = ctx.text_extents(label)
                    lw, lh = lte[2], lte[3]
                    inner_w = unit_track_w - 4 * scale
                    if lw <= inner_w:
                        # Text fits horizontally: center in box
                        ctx.set_source_rgb(*style_cfg.get('text_color', (0.15, 0.15, 0.15)))
                        ctx.move_to(x0 + (unit_track_w - lw) / 2, y1 + hh / 2 + lh / 4)
                        ctx.show_text(label)
                    elif hh >= lw + 4 * scale:
                        # Rotate -90° (reads upward), centered in box
                        ctx.translate(x0 + unit_track_w / 2 + lh / 2,
                                      y1 + hh / 2 + lw / 2)
                        ctx.rotate(-np.pi / 2)
                        ctx.set_source_rgb(*style_cfg.get('text_color', (0.15, 0.15, 0.15)))
                        ctx.move_to(-lw / 2, lh / 4)
                        ctx.show_text(label)
                    # else: box too small in both orientations — skip
                    ctx.restore()
            # Column header: rotated -90° (reads upward), drawn in the header band above y_top
            ctx.save()
            ctx.select_font_face(style_cfg['font_family'],
                                  _to_cairo_slant(style_cfg.get('font_style')),
                                  cairo.FONT_WEIGHT_BOLD)
            ctx.set_font_size(style_cfg['unit_text_size'])
            hte = ctx.text_extents(col_name.title())
            hw, hh_font = hte[2], hte[3]
            header_cx = x0 + unit_track_w / 2
            header_cy = panel_margin + _header_band / 2
            ctx.translate(header_cx, header_cy)
            ctx.rotate(-np.pi / 2)
            ctx.set_source_rgb(*style_cfg.get('text_color', (0.15, 0.15, 0.15)))
            ctx.move_to(-hw / 2, hh_font / 2)
            ctx.show_text(col_name.title())
            ctx.restore()

    if mode in ('annotations', 'annotation_size'):
        marker_size = annotation_size_override if annotation_size_override is not None else (10.0 if mode == 'annotation_size' else 7.0)
        ann_x = col_right_max + 12 * style_cfg['font_scale']
        for _, row in ann_df.iterrows():
            h = float(row['height'])
            if h < y_min or h > y_max:
                continue
            y_ann = y_top + y_span - (h - y_min) * y_scale
            if y_ann <= y_top + 1 or y_ann >= y_top + y_span - 1:
                continue

            r = max(2.2, 0.22 * marker_size * style_cfg['font_scale'])
            ctx.set_source_rgb(0.1, 0.1, 0.1)
            ctx.arc(ann_x, y_ann, r, 0, 2 * np.pi)
            ctx.fill()
            ctx.set_line_width(max(0.9, 0.11 * marker_size))
            ctx.move_to(ann_x + r + 1, y_ann)
            ctx.line_to(ann_x + marker_size * style_cfg['font_scale'], y_ann)
            ctx.stroke()

            _draw_text(ctx, ann_x + marker_size * style_cfg['font_scale'] + 3 * style_cfg['font_scale'], y_ann + 2.5 * style_cfg['font_scale'], row['annotation'], style_cfg['annotation_text_size'], style_cfg)

    if mode == 'strat_data':
        x_d13c = section_left + section_w + gap
        x_d18o = x_d13c + data_w + gap
        _draw_data_track(ctx, x_d13c, y_top, data_w, y_span, y_min, y_max, chemo_df['CARB_d13C'], chemo_df['CARB_HEIGHT'], 'd13C', 'permil', style_cfg)
        _draw_data_track(ctx, x_d18o, y_top, data_w, y_span, y_min, y_max, chemo_df['CARB_d18O'], chemo_df['CARB_HEIGHT'], 'd18O', 'permil', style_cfg)

    surf.finish()
    if show:
        display(SVGDisplay(filename=str(output_path)))












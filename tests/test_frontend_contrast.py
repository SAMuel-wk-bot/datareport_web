def relative_luminance(hex_color):
    channels = [int(hex_color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
    converted = [channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4 for channel in channels]
    return 0.2126 * converted[0] + 0.7152 * converted[1] + 0.0722 * converted[2]


def contrast_ratio(foreground, background):
    lighter, darker = sorted([relative_luminance(foreground), relative_luminance(background)], reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def test_distribution_interface_colors_meet_wcag_aa():
    pairs = [
        ("#ffffff", "#7026b9"),
        ("#501584", "#ffffff"),
        ("#4b137d", "#f6f0fb"),
        ("#ffffff", "#5a1b96"),
        ("#e4c9ff", "#210641"),
    ]
    assert all(contrast_ratio(foreground, background) >= 4.5 for foreground, background in pairs)
